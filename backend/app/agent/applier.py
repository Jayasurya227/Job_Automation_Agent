"""
Module: applier.py
Purpose: Step 4.2 Playwright Easy Apply Form Filler & Screening Q&A Integration.
Standards: Rule 1 (Zero Blind Trust - Robust selectors, explicit error logging, snapshots before submit),
           Rule 2 (Type & Schema Safety),
           Rule 3 (Low Code & High Signal),
           Rule 4 (Assisted Mode Review Gateway),
           Rule 5 (Production Reliability across mock & live portals).
"""
import os
import re
import time
import random
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field

from playwright.sync_api import sync_playwright, Page

try:
    from app.config import DATA_DIR, OUTPUT_DIR
    from app.agent.scorer import load_profile
    from app.agent.qa_bank import get_or_generate_answer
    from app.agent.browser import DEFAULT_USER_AGENT, sanitize_session_preferences
    from app.agent.stealth import (
        build_stealth_js,
        get_stealth_chromium_args,
        get_random_fingerprint,
        HumanInteractionEngine,
        check_bot_challenge,
    )
except ImportError:
    from ..config import DATA_DIR, OUTPUT_DIR
    from .scorer import load_profile
    from .qa_bank import get_or_generate_answer
    from .browser import DEFAULT_USER_AGENT, sanitize_session_preferences
    from .stealth import (
        build_stealth_js,
        get_stealth_chromium_args,
        get_random_fingerprint,
        HumanInteractionEngine,
        check_bot_challenge,
    )

logger = logging.getLogger("applier")

# Snapshots live under the backend's output dir (served by main.py at /output), not the process CWD
SNAPSHOT_DIR = OUTPUT_DIR / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


class FieldMatchResult(BaseModel):
    field_name: str
    field_type: str
    value_filled: str
    selector_used: str


class FormFillResult(BaseModel):
    status: str = Field(description="READY_FOR_REVIEW, SUBMITTED, or ERROR")
    thread_id: str
    job_title: str = ""
    company_name: str = ""
    snapshot_path: Optional[str] = None
    confirmation_snapshot_path: Optional[str] = None
    filled_fields: List[FieldMatchResult] = Field(default_factory=list)
    steps_traversed: int = 0
    error_message: Optional[str] = None


class EasyApplyFiller:
    """
    Intelligent form automation for multi-step Easy Apply applications.
    Coordinates DOM input detection, Q&A memory bank queries, file uploads,
    stepper navigation, and visual snapshot generation.
    """

    def __init__(self, headless: bool = True):
        self.headless = headless
        self.profile = load_profile()
        self.strict = False
        self.unanswered: List[str] = []
        self.current_job_title = ""
        self.current_company_name = ""

    def _lookup_answer(
        self,
        label_text: str,
        allow_ai: bool = True,
        field_type: str = "text",
        options: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        Answer from the Q&A bank / profile backed by Claude Haiku Brain.
        Screening questions are dynamically resolved with Claude Haiku from profile.json.
        """
        ans = get_or_generate_answer(
            question=label_text,
            job_title=getattr(self, "current_job_title", ""),
            company_name=getattr(self, "current_company_name", ""),
            field_type=field_type,
            options=options,
            allow_ai_generation=True,
            verified_only=False,
        )
        if ans is None:
            self.unanswered.append(label_text)
            return None
        return str(ans.get("answer", ""))

    def _resolve_candidate_value(self, label_text: str, input_name: str = "") -> Tuple[str, str]:
        """
        Determines the appropriate value for a text input based on label/name semantics.
        Returns (value, field_type).
        """
        combined = f"{label_text} {input_name}".lower()

        # Name fields
        if re.search(r"(full\s*name|your\s*name|candidate\s*name)", combined):
            return self.profile.personal_info.name, "name"
        if re.search(r"(first\s*name|given\s*name)", combined):
            return self.profile.personal_info.name.split()[0], "first_name"
        if re.search(r"(last\s*name|family\s*name|surname)", combined):
            parts = self.profile.personal_info.name.split()
            return parts[-1] if len(parts) > 1 else "", "last_name"

        # Contact info
        if re.search(r"(email|e-mail)", combined):
            return self.profile.personal_info.email, "email"
        if re.search(r"(phone|mobile|cell|contact\s*number)", combined):
            return self.profile.personal_info.phone, "phone"
        if re.search(r"(location|city|residence|address)", combined):
            return self.profile.personal_info.location, "location"

        # URLs
        if re.search(r"(linkedin)", combined):
            return str(self.profile.personal_info.linkedin_url or ""), "linkedin"
        if re.search(r"(github)", combined):
            return str(self.profile.personal_info.github_url or ""), "github"
        if re.search(r"(portfolio|website)", combined):
            return self.profile.personal_info.portfolio_url or "https://github.com/your-username", "portfolio"

        # Experience & Salary numbers
        if re.search(r"(years.*experience|experience.*years)", combined):
            ans = self._lookup_answer(label_text, allow_ai=True, field_type="number")
            return ("" if ans is None else ans), ("unanswered" if ans is None else "experience")
        if re.search(r"(expected\s*(ctc|salary)|salary\s*expectation)", combined):
            return self.profile.preferences.min_expected_salary or "Negotiable", "salary"

        # General / Screening questions -> Consult Q&A Bank with Claude Brain
        ans = self._lookup_answer(label_text, allow_ai=True, field_type="text")
        return ("" if ans is None else ans), ("unanswered" if ans is None else "screening")

    def fill_visible_step(self, page: Page, resume_path: Optional[str] = None) -> List[FieldMatchResult]:
        """
        Scans and populates all interactive form controls currently visible on the page.
        """
        filled_records: List[FieldMatchResult] = []

        # 1. Text, Email, Tel, and Number inputs
        text_inputs = page.query_selector_all("input[type='text']:visible, input[type='email']:visible, input[type='tel']:visible, input[type='number']:visible, input:not([type]):visible")
        for inp in text_inputs:
            try:
                # Check if already has value
                current_val = inp.input_value()
                if current_val and current_val.strip():
                    continue

                inp_id = inp.get_attribute("id") or ""
                inp_name = inp.get_attribute("name") or ""
                placeholder = inp.get_attribute("placeholder") or ""

                # Look for associated label
                label_text = ""
                if inp_id:
                    lbl = page.query_selector(f"label[for='{inp_id}']")
                    if lbl:
                        label_text = lbl.inner_text().strip()

                if not label_text:
                    label_text = placeholder or inp_name

                val_to_fill, f_type = self._resolve_candidate_value(label_text, inp_name)
                if f_type == "unanswered":
                    continue
                # Humanized typing cadence for inputs
                try:
                    inp.click()
                    page.wait_for_timeout(random.randint(50, 120))
                    inp.fill("")
                    if len(val_to_fill) <= 50:
                        for char in val_to_fill:
                            inp.type(char)
                            page.wait_for_timeout(random.randint(15, 45))
                    else:
                        inp.fill(val_to_fill)
                except Exception:
                    inp.fill(val_to_fill)

                filled_records.append(FieldMatchResult(
                    field_name=label_text or inp_name or inp_id,
                    field_type=f_type,
                    value_filled=val_to_fill,
                    selector_used=f"#{inp_id}" if inp_id else f"input[name='{inp_name}']"
                ))
            except Exception as e:
                logger.debug(f"Could not fill text input: {e}")

        # 2. Textareas (Screening & Open-Ended questions)
        textareas = page.query_selector_all("textarea:visible")
        for ta in textareas:
            try:
                if ta.input_value().strip():
                    continue
                ta_id = ta.get_attribute("id") or ""
                ta_name = ta.get_attribute("name") or ""
                lbl_text = ""
                if ta_id:
                    lbl = page.query_selector(f"label[for='{ta_id}']")
                    if lbl:
                        lbl_text = lbl.inner_text().strip()
                if not lbl_text:
                    lbl_text = ta.get_attribute("placeholder") or ta_name or "Why are you interested in this role?"

                val_to_fill = self._lookup_answer(lbl_text, allow_ai=True)
                if val_to_fill is None:
                    continue
                
                # Human pause & fill simulation for detailed answers
                try:
                    ta.click()
                    page.wait_for_timeout(random.randint(80, 160))
                    ta.fill(val_to_fill)
                    page.wait_for_timeout(random.randint(50, 120))
                except Exception:
                    ta.fill(val_to_fill)

                filled_records.append(FieldMatchResult(
                    field_name=lbl_text,
                    field_type="textarea_qa",
                    value_filled=val_to_fill[:60] + "...",
                    selector_used=f"#{ta_id}" if ta_id else f"textarea[name='{ta_name}']"
                ))
            except Exception as e:
                logger.debug(f"Could not fill textarea: {e}")

        # 3. Select Dropdowns
        selects = page.query_selector_all("select:visible")
        for sel in selects:
            try:
                sel_id = sel.get_attribute("id") or ""
                sel_name = sel.get_attribute("name") or ""
                lbl_text = ""
                if sel_id:
                    lbl = page.query_selector(f"label[for='{sel_id}']")
                    if lbl:
                        lbl_text = lbl.inner_text().strip()
                if not lbl_text:
                    lbl_text = sel_name

                # Check options
                options = sel.query_selector_all("option")
                opt_texts = [o.inner_text().strip() for o in options if o.get_attribute("value")]
                
                # Match against Q&A bank with Claude Haiku Brain
                qa_answer = self._lookup_answer(lbl_text, allow_ai=True, field_type="select", options=opt_texts)
                if qa_answer is None:
                    continue
                target_ans = qa_answer.lower()
                
                # Find best matching option
                chosen_opt = None
                for opt in options:
                    otext = opt.inner_text().lower()
                    oval = (opt.get_attribute("value") or "").lower()
                    if target_ans in otext or target_ans in oval or ("immediate" in target_ans and "immediate" in otext):
                        chosen_opt = opt.get_attribute("value")
                        break

                if not chosen_opt and len(options) > 1:
                    # Pick first non-empty option
                    chosen_opt = options[1].get_attribute("value")

                if chosen_opt:
                    sel.select_option(value=chosen_opt)
                    filled_records.append(FieldMatchResult(
                        field_name=lbl_text,
                        field_type="select",
                        value_filled=chosen_opt,
                        selector_used=f"#{sel_id}" if sel_id else f"select[name='{sel_name}']"
                    ))
            except Exception as e:
                logger.debug(f"Could not fill select: {e}")

        # 4. Radio Buttons (Work Auth, Sponsorship, Relocation)
        radio_groups = page.query_selector_all("input[type='radio']:visible")
        processed_groups = set()
        for rb in radio_groups:
            r_name = rb.get_attribute("name") or ""
            if not r_name or r_name in processed_groups:
                continue
            processed_groups.add(r_name)

            try:
                # Find question label near radio group
                group_lbl = ""
                parent = rb.evaluate_handle("el => el.closest('.form-group') || el.parentElement.parentElement")
                if parent:
                    p_elem = parent.as_element()
                    if p_elem:
                        lbl_el = p_elem.query_selector("label:not(.radio-label)")
                        if lbl_el:
                            group_lbl = lbl_el.inner_text().strip()

                if not group_lbl:
                    group_lbl = r_name

                all_radios = page.query_selector_all(f"input[type='radio'][name='{r_name}']:visible")
                radio_options = []
                for rad in all_radios:
                    rad_id = rad.get_attribute("id") or ""
                    lbl_for_rad = page.query_selector(f"label[for='{rad_id}']")
                    rad_text = lbl_for_rad.inner_text().strip() if lbl_for_rad else (rad.get_attribute("value") or "")
                    if rad_text:
                        radio_options.append(rad_text)

                answer = self._lookup_answer(group_lbl, allow_ai=True, field_type="radio", options=radio_options)
                if answer is None:
                    continue
                desired_val = answer.lower()

                # Find radio options for this group
                selected_val = ""
                for rad in all_radios:
                    val = (rad.get_attribute("value") or "").lower()
                    rad_id = rad.get_attribute("id") or ""
                    # Check text inside radio label
                    lbl_for_rad = page.query_selector(f"label[for='{rad_id}']")
                    rad_text = lbl_for_rad.inner_text().lower() if lbl_for_rad else ""

                    if desired_val in val or desired_val in rad_text or (desired_val == "yes" and "yes" in val):
                        rad.check()
                        selected_val = rad.get_attribute("value") or "Yes"
                        break

                if not selected_val and all_radios:
                    all_radios[0].check()
                    selected_val = all_radios[0].get_attribute("value") or "Checked"

                filled_records.append(FieldMatchResult(
                    field_name=group_lbl,
                    field_type="radio",
                    value_filled=selected_val,
                    selector_used=f"input[name='{r_name}']"
                ))
            except Exception as e:
                logger.debug(f"Could not handle radio group: {e}")

        # 5. File Uploads (Resume Attachment)
        file_inputs = page.query_selector_all("input[type='file']:visible, input[type='file']")
        for fi in file_inputs:
            try:
                # Only ever upload the candidate's real resume. No placeholder fallback.
                if not resume_path or not Path(resume_path).exists():
                    logger.warning("No resume PDF available; skipping file upload field.")
                    continue
                target_file = str(Path(resume_path).resolve())

                fi.set_input_files(target_file)
                filled_records.append(FieldMatchResult(
                    field_name="Resume Upload",
                    field_type="file_upload",
                    value_filled=Path(target_file).name,
                    selector_used="input[type='file']"
                ))
            except Exception as e:
                logger.debug(f"Could not upload resume file: {e}")

        return filled_records

    def find_and_click_next(self, page: Page) -> Tuple[bool, bool]:
        """
        Identifies step progression buttons.
        Returns (advanced_to_next_step, is_final_submit_step).
        """
        # Selectors for submission/review
        submit_selectors = [
            "button#btn-submit-application:visible",
            "button:has-text('Submit application'):visible",
            "button:has-text('Submit'):visible",
            "button[aria-label*='Submit']:visible",
        ]

        # Check if final submit button is currently visible
        for s_sel in submit_selectors:
            submit_btn = page.query_selector(s_sel)
            if submit_btn and submit_btn.is_visible():
                return False, True

        # Selectors for 'Next' / 'Review'
        next_selectors = [
            "button#btn-next-step-1:visible",
            "button#btn-next-step-2:visible",
            "button:has-text('Review Application'):visible",
            "button:has-text('Review your application'):visible",
            "button:has-text('Next Step'):visible",
            "button:has-text('Next'):visible",
            "button:has-text('Continue to next step'):visible",
            "button[aria-label*='Continue']:visible",
            "button[aria-label*='Next']:visible",
        ]

        for n_sel in next_selectors:
            next_btn = page.query_selector(n_sel)
            if next_btn and next_btn.is_visible():
                try:
                    HumanInteractionEngine.human_click_sync(page, n_sel)
                except Exception:
                    next_btn.click()
                page.wait_for_timeout(random.randint(300, 600))

                # Check if this click landed us on submit screen
                for s_sel in submit_selectors:
                    sub = page.query_selector(s_sel)
                    if sub and sub.is_visible():
                        return True, True
                return True, False

        return False, False

    def _apply_naukri_live(
        self,
        page: Page,
        context: Any,
        target_url: str,
        job_title: str,
        company_name: str,
        tid: str,
        snapshot_file: Path,
        confirmed_snapshot_file: Path,
        auto_submit: bool = False,
    ) -> FormFillResult:
        """
        Specialized live Naukri applicant engine.
        Inherits authenticated browser session cookies from backend/data/browser_session/.
        Handles Already Applied, Login Required, Company Site Redirection, and Questionnaire drawers.
        """
        self.current_job_title = job_title
        self.current_company_name = company_name

        logger.info(f"[{tid}] Warming authenticated session via Naukri Homepage...")
        try:
            page.goto("https://www.naukri.com/mnjuser/homepage", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
        except Exception as warm_err:
            logger.debug(f"[{tid}] Session warm-up notice: {warm_err}")

        logger.info(f"[{tid}] Navigating to live Naukri posting: {target_url}")
        try:
            page.goto(target_url, timeout=35000, wait_until="load")
            page.wait_for_timeout(random.randint(2500, 3500))
        except Exception as nav_err:
            logger.error(f"[{tid}] Failed to reach Naukri listing: {nav_err}")
            context.close()
            return FormFillResult(
                status="NAVIGATION_FAILED",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message=f"Live Naukri navigation error: {str(nav_err)}"
            )

        # 1. Anti-Bot Challenge Check
        challenge = check_bot_challenge(page)
        if challenge:
            logger.warning(f"[{tid}] Naukri bot challenge detected: {challenge}")
            context.close()
            return FormFillResult(
                status="BOT_CHALLENGE",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message=f"Naukri verification required: {challenge}"
            )

        # 2. Already Applied Check
        already_applied_selectors = [
            ".already-applied",
            "button:has-text('Already Applied')",
            "span:has-text('Already Applied')",
            ".applied-message",
        ]
        for sel in already_applied_selectors:
            elem = page.query_selector(sel)
            if elem and elem.is_visible():
                logger.info(f"[{tid}] Job already applied on Naukri.")
                context.close()
                return FormFillResult(
                    status="SUBMITTED",
                    thread_id=tid,
                    job_title=job_title,
                    company_name=company_name,
                    error_message="Already marked as applied on candidate Naukri account."
                )

        # 3. Check if Login is Required (Session missing/expired)
        if page.query_selector("a#login_Layer:visible, .login-btn:visible, a:has-text('Login to apply'):visible"):
            logger.warning(f"[{tid}] Naukri session not detected. Login required.")
            context.close()
            return FormFillResult(
                status="LOGIN_REQUIRED",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message="Naukri session not authenticated. Please click 'Connect Naukri' in Settings to log in."
            )

        # 4. External Company Site Check
        company_site_btn = page.query_selector("button:has-text('Apply on company site'), a:has-text('Apply on company site'), .company-site-button")
        if company_site_btn and company_site_btn.is_visible():
            logger.info(f"[{tid}] Naukri posting redirects to external company portal. Skipping 1-Click apply.")
            context.close()
            return FormFillResult(
                status="EXTERNAL_SITE",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message="Listing redirects to external employer ATS portal."
            )

        # 5. Locate 1-Click Apply Button
        apply_selectors = [
            "button#apply-button:visible",
            "button.apply-button:visible",
            ".apply-button:visible",
            "button:has-text('Apply on Naukri'):visible",
            "button:has-text('Apply'):visible",
            "a#apply-button:visible",
            "a.apply-button:visible",
            "a:has-text('Apply on Naukri'):visible",
            "a:has-text('Apply'):visible",
            "button:has-text('I am interested'):visible",
        ]
        apply_btn = None
        apply_sel_used = None
        for sel in apply_selectors:
            elem = page.query_selector(sel)
            if elem and elem.is_visible():
                apply_btn = elem
                apply_sel_used = sel
                break

        if not apply_btn:
            logger.warning(f"[{tid}] Could not find active Apply button on Naukri.")
            context.close()
            return FormFillResult(
                status="NO_APPLY_BUTTON",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message="Active Apply button not found on Naukri job card."
            )

        # Pre-Click Watchdog: Check if the apply button itself directly links outside naukri.com
        btn_href = (apply_btn.get_attribute("href") or "").strip()
        if btn_href and btn_href.startswith("http") and "naukri.com" not in btn_href.lower():
            logger.info(f"[{tid}] Apply button href points directly to external portal: {btn_href}. Skipping 1-Click apply.")
            context.close()
            return FormFillResult(
                status="EXTERNAL_SITE",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message=f"Apply button links directly to external portal: {btn_href}"
            )

        if not auto_submit:
            context.close()
            return FormFillResult(
                status="READY_FOR_REVIEW",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                steps_traversed=1
            )

        # 6. Execute Click & Handle Chatbot / Questionnaire Drawer
        logger.info(f"[{tid}] Clicking Naukri Apply button using selector: {apply_sel_used}")
        try:
            HumanInteractionEngine.human_click_sync(page, apply_sel_used)
        except Exception:
            apply_btn.click()

        page.wait_for_timeout(random.randint(2500, 3500))

        # Check for Post-Click External Redirection / Redirection Popup
        # Case A: Current page redirected away from naukri.com
        if "naukri.com" not in page.url.lower():
            logger.info(f"[{tid}] Post-click navigation redirected to external portal: {page.url}. Skipping 1-Click apply.")
            context.close()
            return FormFillResult(
                status="EXTERNAL_SITE",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message=f"Post-click redirected to external ATS portal: {page.url}"
            )

        # Case B: A new tab / popup was opened pointing outside naukri.com
        if len(context.pages) > 1:
            for p in context.pages[1:]:
                if "naukri.com" not in p.url.lower():
                    logger.info(f"[{tid}] External career portal tab opened: {p.url}. Closing and tagging External.")
                    p.close()
                    context.close()
                    return FormFillResult(
                        status="EXTERNAL_SITE",
                        thread_id=tid,
                        job_title=job_title,
                        company_name=company_name,
                        error_message="Clicking Apply opened an external employer career site."
                    )

        # Case C: An in-page modal/popup informing the user about external redirection
        redirect_modal = page.query_selector(
            "div:has-text('redirected to the employer'), "
            "div:has-text('redirected to employer'), "
            "div:has-text('redirected to company'), "
            "div:has-text('redirect to external site'), "
            "div:has-text('Apply on employer website'), "
            "div:has-text('Apply on company site'), "
            "div:has-text('external career site'), "
            "div:has-text('career website'), "
            "button:has-text('Go to company site'), "
            "button:has-text('Proceed to company site'), "
            "button:has-text('Continue to apply'), "
            "a:has-text('Go to company site'), "
            "a:has-text('Proceed to company site')"
        )
        if redirect_modal and redirect_modal.is_visible():
            logger.info(f"[{tid}] External redirection confirmation modal detected. Tagging External.")
            context.close()
            return FormFillResult(
                status="EXTERNAL_SITE",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message="Employer requires external redirection to complete application."
            )

        # Check for immediate application success banner (Direct 1-Click without questions)
        immediate_success = page.query_selector(
            ".already-applied:visible, "
            ".applied-message:visible, "
            "div:has-text('Application sent'):visible, "
            "div:has-text('successfully applied'):visible, "
            "div:has-text('Applied successfully'):visible"
        )
        if immediate_success:
            logger.info(f"[{tid}] Immediate application success message detected on page!")
            try:
                page.screenshot(path=str(confirmed_snapshot_file), full_page=False)
            except Exception:
                pass
            context.close()
            return FormFillResult(
                status="SUBMITTED",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                confirmation_snapshot_path=str(confirmed_snapshot_file),
                steps_traversed=1
            )

        # Check for questionnaire drawer or modern conversational chatbot
        drawer_sel = "._chatBotContainer, .chatbot_drawer, .drawer-wrapper, .apply-modal-wrapper, .bot-drawer"
        drawer = page.query_selector(drawer_sel)
        if drawer and drawer.is_visible():
            logger.info(f"[{tid}] Naukri questionnaire drawer detected. Auto-answering screening fields with AI LLM Brain...")
            for turn in range(1, 10):
                page.wait_for_timeout(1500)
                cb = page.query_selector(drawer_sel)
                if not cb or not cb.is_visible():
                    logger.info(f"[{tid}] Drawer closed or completed.")
                    break

                cb_raw = cb.inner_text() or ""
                cb_text = cb_raw.lower()
                if any(w in cb_text for w in ["successfully applied", "application sent", "applied for the job", "applied to this job", "has been sent"]):
                    logger.info(f"[{tid}] Application success message detected in chatbot!")
                    break

                # Extract latest question text from drawer
                q_candidates = cb.query_selector_all(".botMsg, .bot-msg, .chat-bubble, .server-msg, .question-text, .msg, .ssrc__sub-title")
                question_text = ""
                if q_candidates:
                    for qc in reversed(q_candidates):
                        txt = (qc.inner_text() or "").strip()
                        if txt and len(txt) > 3 and not any(k in txt.lower() for k in ["save", "submit", "skip"]):
                            question_text = txt
                            break
                if not question_text:
                    lines = [ln.strip() for ln in cb_raw.splitlines() if ln.strip()]
                    if lines:
                        for ln in reversed(lines):
                            if len(ln) > 5 and not any(k in ln.lower() for k in ["save", "submit", "apply", "cancel"]):
                                question_text = ln
                                break

                # 1. Radio / pill options (MCQs)
                labels = cb.query_selector_all("label.ssrc__label, .ssrc__radio-btn-container, [role='radio']")
                chosen = None

                if labels:
                    opt_texts = [(l.inner_text() or "").strip() for l in labels if (l.inner_text() or "").strip()]
                    logger.info(f"[{tid}] Chatbot Screening Question: '{question_text}' | Options: {opt_texts}")

                    # Consult Claude Haiku LLM Brain via Q&A Bank
                    ai_answer = None
                    try:
                        ai_answer = self._lookup_answer(
                            label_text=question_text or "Screening Question",
                            allow_ai=True,
                            field_type="radio",
                            options=opt_texts,
                        )
                    except Exception as ai_err:
                        logger.warning(f"[{tid}] AI screening answer lookup notice: {ai_err}")

                    if ai_answer:
                        ai_ans_clean = str(ai_answer).strip().lower()
                        logger.info(f"[{tid}] AI Brain selected option: '{ai_answer}'")
                        # 1a. Exact match
                        for l in labels:
                            lt = (l.inner_text() or "").strip().lower()
                            if lt == ai_ans_clean:
                                chosen = l
                                break
                        # 1b. Fuzzy / substring match
                        if not chosen:
                            for l in labels:
                                lt = (l.inner_text() or "").strip().lower()
                                if ai_ans_clean in lt or lt in ai_ans_clean:
                                    chosen = l
                                    break

                    # 1c. Heuristic candidate preference fallback if LLM returned None
                    if not chosen:
                        for pref in ["0-1 years", "1-2 years", "yes", "immediate", "15 days", "15 days or less"]:
                            for l in labels:
                                if pref in (l.inner_text() or "").strip().lower():
                                    chosen = l
                                    break
                            if chosen:
                                break

                    # 1d. Final fallback to first option
                    if not chosen:
                        chosen = labels[0]

                    if chosen:
                        try:
                            box = chosen.bounding_box()
                            if box:
                                page.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
                            else:
                                chosen.click()
                        except Exception as click_err:
                            logger.debug(f"[{tid}] Option click notice: {click_err}")
                        page.wait_for_timeout(1000)

                # 2. Check for written text or number inputs or textareas in chatbot drawer
                text_inps = cb.query_selector_all("input[type='text']:visible, input[type='number']:visible, textarea:visible")
                for inp in text_inps:
                    if (inp.input_value() or "").strip():
                        continue
                    f_type = inp.get_attribute("type") or ("number" if "number" in (inp.get_attribute("inputmode") or "") else "text")
                    val = self._lookup_answer(label_text=question_text or "Candidate Screening Response", allow_ai=True, field_type=f_type)
                    fill_val = val if val else ("1" if f_type == "number" else "Yes, proficient and experienced.")
                    val_str = str(fill_val)
                    try:
                        inp.click()
                        page.wait_for_timeout(random.randint(80, 160))
                        # Select all and delete to clear existing value
                        page.keyboard.press("Control+A")
                        page.keyboard.press("Backspace")
                        page.wait_for_timeout(random.randint(30, 70))
                        if len(val_str) <= 300:
                            for ch in val_str:
                                inp.type(ch)
                                page.wait_for_timeout(random.randint(12, 35))
                        else:
                            inp.fill(val_str)
                        logger.info(f"[{tid}] Human-typed written answer into chatbot: '{val_str}'")
                    except Exception as fill_err:
                        logger.debug(f"[{tid}] Chatbot input fill notice: {fill_err}")
                        try:
                            inp.fill(val_str)
                        except Exception:
                            pass
                    page.wait_for_timeout(600)

                # 3. Check for select dropdowns in drawer
                select_els = cb.query_selector_all("select:visible")
                for s_el in select_els:
                    opt_tags = s_el.query_selector_all("option")
                    select_opts = [(o.inner_text() or "").strip() for o in opt_tags if (o.inner_text() or "").strip()]
                    if select_opts:
                        ans = self._lookup_answer(label_text=question_text or "Screening Selection", allow_ai=True, field_type="select", options=select_opts)
                        if ans:
                            for o in opt_tags:
                                if (o.inner_text() or "").strip().lower() == ans.lower():
                                    s_el.select_option(value=o.get_attribute("value") or ans)
                                    logger.info(f"[{tid}] Selected dropdown option: '{ans}'")
                                    break

                # 4. Click Save / Submit in drawer
                save_selectors = [
                    ".sendMsgbtn_container:visible",
                    ".sendMsg:visible",
                    "button:has-text('Save & Apply'):visible",
                    "button:has-text('Save'):visible",
                    "button:has-text('Submit'):visible",
                    "button:has-text('Apply'):visible",
                    "button:has-text('Next'):visible",
                    "[class*='sendMsg']:visible",
                    "[class*='saveBtn']:visible",
                    "span:has-text('Save'):visible",
                    "a:has-text('Save'):visible",
                ]
                save_el = None
                for sel in save_selectors:
                    elem = cb.query_selector(sel)
                    if elem and elem.is_visible():
                        save_el = elem
                        break

                if save_el:
                    try:
                        s_box = save_el.bounding_box()
                        if s_box:
                            page.mouse.click(s_box["x"] + s_box["width"]/2, s_box["y"] + s_box["height"]/2)
                        else:
                            save_el.click()
                    except Exception as save_err:
                        logger.debug(f"[{tid}] Save click notice: {save_err}")
                    page.wait_for_timeout(2500)

        page.wait_for_timeout(2000)
        try:
            page.screenshot(path=str(confirmed_snapshot_file), full_page=False)
        except Exception:
            pass

        context.close()
        logger.info(f"[{tid}] Naukri application submitted successfully.")

        return FormFillResult(
            status="SUBMITTED",
            thread_id=tid,
            job_title=job_title,
            company_name=company_name,
            confirmation_snapshot_path=str(confirmed_snapshot_file),
            steps_traversed=1
        )

    def _apply_indeed_live(
        self,
        page: Page,
        context: Any,
        target_url: str,
        job_title: str,
        company_name: str,
        resume_path: Optional[str],
        tid: str,
        snapshot_file: Path,
        confirmed_snapshot_file: Path,
        auto_submit: bool = False,
    ) -> FormFillResult:
        """
        Specialized live Indeed applicant engine.
        Inherits authenticated browser session cookies from backend/data/indeed_session/.
        Handles Already Applied, Login Required, Company Site Redirection, and multi-step Easily Apply modals.
        """
        logger.info(f"[{tid}] Navigating to live Indeed posting: {target_url}")
        try:
            page.goto(target_url, timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(random.randint(2000, 3000))
        except Exception as nav_err:
            logger.error(f"[{tid}] Failed to reach Indeed listing: {nav_err}")
            context.close()
            return FormFillResult(
                status="NAVIGATION_FAILED",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message=f"Live Indeed navigation error: {str(nav_err)}"
            )

        # 1. Anti-Bot Challenge Check
        challenge = check_bot_challenge(page)
        if challenge:
            logger.warning(f"[{tid}] Indeed bot challenge detected: {challenge}")
            context.close()
            return FormFillResult(
                status="BOT_CHALLENGE",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message=f"Indeed verification required: {challenge}"
            )

        # 2. Already Applied Check
        already_applied_selectors = [
            "[data-testid='applied-badge']",
            "button:has-text('Applied')",
            "span:has-text('Applied')",
            ".ia-AppliedMessage",
            "div:has-text('You have applied to this job')",
            "div:has-text('Application submitted')",
        ]
        for sel in already_applied_selectors:
            elem = page.query_selector(sel)
            if elem and elem.is_visible():
                logger.info(f"[{tid}] Job already applied on Indeed.")
                context.close()
                return FormFillResult(
                    status="SUBMITTED",
                    thread_id=tid,
                    job_title=job_title,
                    company_name=company_name,
                    error_message="Already marked as applied on candidate Indeed account."
                )

        # 3. Check if Login is Required (Session missing/expired)
        if page.query_selector(".ia-SignInRequired:visible, div:has-text('Sign in to apply'):visible"):
            logger.warning(f"[{tid}] Indeed session disconnected. Login required.")
            context.close()
            return FormFillResult(
                status="LOGIN_REQUIRED",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message="Indeed session disconnected. Please click 'Launch Safe Login Session' in Settings."
            )

        # 4. External Company Site Check
        company_site_btn = page.query_selector(
            "button:has-text('Apply on company site'):visible, "
            "a:has-text('Apply on company site'):visible, "
            "button:has-text('Apply on employer site'):visible, "
            "a:has-text('Apply on employer site'):visible"
        )
        if company_site_btn and not page.query_selector("#indeedApplyButton:visible, button:has-text('Easily apply'):visible, button:has-text('Apply now'):visible"):
            logger.info(f"[{tid}] Indeed posting redirects to external company portal. Skipping 1-Click apply.")
            context.close()
            return FormFillResult(
                status="EXTERNAL_SITE",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message="Listing redirects to external employer ATS portal."
            )

        # 5. Locate 1-Click "Apply now" / "Easily apply" button
        apply_selectors = [
            "button#indeedApplyButton:visible",
            "button.ia-IndeedApplyButton:visible",
            "[data-testid='indeedApplyButton']:visible",
            "button:has-text('Easily apply'):visible",
            "button:has-text('Apply now'):visible",
            "a#indeedApplyButton:visible",
            "a:has-text('Easily apply'):visible",
            "a:has-text('Apply now'):visible",
        ]
        apply_btn = None
        apply_sel_used = None
        for sel in apply_selectors:
            elem = page.query_selector(sel)
            if elem and elem.is_visible():
                apply_btn = elem
                apply_sel_used = sel
                break

        if not apply_btn:
            logger.warning(f"[{tid}] Could not find active 'Easily Apply' button on Indeed.")
            context.close()
            return FormFillResult(
                status="NO_APPLY_BUTTON",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                error_message="Active 'Easily Apply' button not found on Indeed job card."
            )

        if not auto_submit:
            try:
                page.screenshot(path=str(snapshot_file), full_page=False)
            except Exception:
                pass
            context.close()
            return FormFillResult(
                status="READY_FOR_REVIEW",
                thread_id=tid,
                job_title=job_title,
                company_name=company_name,
                snapshot_path=str(snapshot_file),
                steps_traversed=1
            )

        # 6. Execute Click on "Easily Apply" & Handle Multi-Step Modal
        logger.info(f"[{tid}] Clicking Indeed 'Easily Apply' button using selector: {apply_sel_used}")
        try:
            HumanInteractionEngine.human_click_sync(page, apply_sel_used)
        except Exception:
            apply_btn.click()

        page.wait_for_timeout(random.randint(2500, 3500))

        # Indeed application modal stepper loop (max 7 steps: Contact -> Resume -> Q&A -> Review -> Submit)
        step_idx = 0
        filled_fields: List[FieldMatchResult] = []
        p_info = self.profile.personal_info
        p_name = p_info.name or "Candidate"
        p_email = p_info.email or ""
        p_phone = p_info.phone or ""
        p_city = p_info.location if isinstance(p_info.location, str) and p_info.location else "Hyderabad"

        while step_idx < 7:
            step_idx += 1
            page.wait_for_timeout(random.randint(1200, 2000))

            # A. Fill contact inputs if present
            name_input = page.query_selector("input[id*='name']:visible, input[name*='name']:visible")
            if name_input and not name_input.input_value():
                name_input.fill(p_name)
                filled_fields.append(FieldMatchResult(field_name="Full Name", field_type="text", value_filled=p_name, selector_used="name"))

            phone_input = page.query_selector("input[type='tel']:visible, input[id*='phone']:visible, input[name*='phone']:visible")
            if phone_input and not phone_input.input_value():
                phone_input.fill(p_phone)
                filled_fields.append(FieldMatchResult(field_name="Phone", field_type="tel", value_filled=p_phone, selector_used="phone"))

            city_input = page.query_selector("input[id*='location']:visible, input[name*='city']:visible, input[id*='city']:visible")
            if city_input and not city_input.input_value():
                city_input.fill(p_city)
                filled_fields.append(FieldMatchResult(field_name="City", field_type="text", value_filled=p_city, selector_used="city"))

            # B. Resume Selection & Upload
            resume_radios = page.query_selector_all("input[type='radio'][name*='resume']:visible, [data-testid*='resume-radio']:visible")
            if resume_radios and not any(r.is_checked() for r in resume_radios):
                try:
                    resume_radios[0].click()
                    filled_fields.append(FieldMatchResult(field_name="Saved Resume", field_type="radio", value_filled="Selected default resume", selector_used="resume-radio"))
                except Exception:
                    pass

            file_input = page.query_selector("input[type='file']")
            if file_input and resume_path and Path(resume_path).exists():
                try:
                    file_input.set_input_files(resume_path)
                    logger.info(f"[{tid}] Attached tailored resume: {resume_path}")
                    page.wait_for_timeout(1500)
                    filled_fields.append(FieldMatchResult(field_name="Resume Upload", field_type="file", value_filled=Path(resume_path).name, selector_used="input[type='file']"))
                except Exception as file_err:
                    logger.debug(f"[{tid}] Resume upload notice: {file_err}")

            # C. Dynamic Screening Questions Q&A (Grounded strictly in profile.json / Claude Haiku Brain)
            question_containers = page.query_selector_all(
                ".ia-Questions-item, fieldset, .ia-BasePage-section, [data-testid*='question'], .jobsearch-FormQuestion"
            )
            for q_elem in question_containers:
                label_elem = q_elem.query_selector("legend, label, .ia-Questions-item-label, [data-testid*='label']")
                if not label_elem:
                    continue
                q_text = (label_elem.inner_text() or "").strip()
                if not q_text or len(q_text) < 3:
                    continue

                # 1. Check select dropdowns
                select_elem = q_elem.query_selector("select:visible")
                if select_elem:
                    options = select_elem.query_selector_all("option")
                    opt_texts = [o.inner_text().strip() for o in options if o.get_attribute("value")]
                    ans = self._lookup_answer(q_text, allow_ai=True, field_type="select", options=opt_texts) or (opt_texts[0] if opt_texts else "")
                    target_ans = ans.lower()
                    for opt in options:
                        t = (opt.inner_text() or "").strip().lower()
                        val = opt.get_attribute("value")
                        if target_ans in t or t in target_ans:
                            if val:
                                select_elem.select_option(value=val)
                                filled_fields.append(FieldMatchResult(field_name=q_text[:40], field_type="select", value_filled=t, selector_used="select"))
                                break
                    continue

                # 2. Check radio buttons
                radio_btns = q_elem.query_selector_all("input[type='radio']:visible")
                if radio_btns:
                    radio_options = []
                    for rb in radio_btns:
                        rb_id = rb.get_attribute("id") or ""
                        lbl_for_rb = page.query_selector(f"label[for='{rb_id}']")
                        t = lbl_for_rb.inner_text().strip() if lbl_for_rb else (rb.get_attribute("value") or "")
                        if t:
                            radio_options.append(t)
                    ans = self._lookup_answer(q_text, allow_ai=True, field_type="radio", options=radio_options) or "Yes"
                    desired = ans.lower()
                    for rb in radio_btns:
                        rb_id = rb.get_attribute("id") or ""
                        lbl_for_rb = page.query_selector(f"label[for='{rb_id}']")
                        val = (rb.get_attribute("value") or "").lower()
                        t = (lbl_for_rb.inner_text().lower() if lbl_for_rb else "")
                        if desired in val or desired in t or (desired == "yes" and "yes" in val):
                            rb.click()
                            filled_fields.append(FieldMatchResult(field_name=q_text[:40], field_type="radio", value_filled=desired, selector_used="radio"))
                            break
                    continue

                # 3. Check number inputs
                num_input = q_elem.query_selector("input[type='number']:visible")
                if num_input and not num_input.input_value():
                    ans = self._lookup_answer(q_text, allow_ai=True, field_type="number") or "1"
                    num_input.fill(str(ans))
                    filled_fields.append(FieldMatchResult(field_name=q_text[:40], field_type="number", value_filled=str(ans), selector_used="number"))
                    continue

                # 4. Check text / textarea inputs
                text_input = q_elem.query_selector("textarea:visible, input[type='text']:visible, input:not([type]):visible")
                if text_input and not text_input.input_value():
                    is_numeric_question = bool(re.search(r"(how many|years|experience|notice|ctc|salary|score)", q_text, re.I))
                    f_type = "number" if is_numeric_question else "text"
                    ans = self._lookup_answer(q_text, allow_ai=True, field_type=f_type) or ("1" if is_numeric_question else "Yes")
                    text_input.fill(str(ans))
                    filled_fields.append(FieldMatchResult(field_name=q_text[:40], field_type=f_type, value_filled=str(ans), selector_used="input"))
                    continue

                # 5. Check checkboxes
                checkbox = q_elem.query_selector("input[type='checkbox']:visible")
                if checkbox and not checkbox.is_checked():
                    checkbox.check()
                    filled_fields.append(FieldMatchResult(field_name=q_text[:40], field_type="checkbox", value_filled="checked", selector_used="checkbox"))

            # D. Check if Submit button is reached
            submit_btn = page.query_selector(
                "button:has-text('Submit your application'):visible, "
                "button:has-text('Submit application'):visible, "
                "button:has-text('Submit'):visible, "
                "button[data-testid='submit-button']:visible"
            )
            if submit_btn:
                logger.info(f"[{tid}] Final submission step reached on Indeed. Submitting application...")
                try:
                    submit_btn.click()
                except Exception:
                    page.evaluate("(btn) => btn.click()", submit_btn)

                page.wait_for_timeout(random.randint(2500, 3500))
                try:
                    page.screenshot(path=str(confirmed_snapshot_file), full_page=False)
                except Exception:
                    pass

                context.close()
                logger.info(f"[{tid}] Indeed application successfully submitted!")
                return FormFillResult(
                    status="SUBMITTED",
                    thread_id=tid,
                    job_title=job_title,
                    company_name=company_name,
                    confirmation_snapshot_path=str(confirmed_snapshot_file),
                    filled_fields=filled_fields,
                    steps_traversed=step_idx
                )

            # E. Check for Continue / Next button to advance modal
            continue_btn = page.query_selector(
                "button:has-text('Continue'):visible, "
                "button:has-text('Next'):visible, "
                "button:has-text('Review your application'):visible, "
                "button[data-testid='continue-button']:visible"
            )
            if continue_btn:
                logger.info(f"[{tid}] Advancing Indeed application modal (Step {step_idx})...")
                continue_btn.click()
                page.wait_for_timeout(random.randint(1500, 2500))
            else:
                break

        # Finished loop
        context.close()
        return FormFillResult(
            status="SUBMITTED",
            thread_id=tid,
            job_title=job_title,
            company_name=company_name,
            filled_fields=filled_fields,
            steps_traversed=step_idx
        )

    def fill_and_stage_application(
        self,
        target_url_or_path: str,
        resume_path: Optional[str] = None,
        job_title: str = "Target Job",
        company_name: str = "Hiring Company",
        thread_id: Optional[str] = None,
        auto_submit: bool = False,
    ) -> FormFillResult:
        """
        Main runner: Navigates multi-step form with stealth spoofing & human pacing,
        fills candidate data, checks for bot challenges, takes review snapshot,
        and either pauses for Assisted Review Gateway or executes submission.
        Inherits authenticated browser session from backend/data/browser_session/.
        """
        tid = thread_id or f"app_{int(time.time() * 1000)}"
        snapshot_file = SNAPSHOT_DIR / f"review_{tid}.png"
        confirmed_snapshot_file = SNAPSHOT_DIR / f"confirmed_{tid}.png"

        self.current_job_title = job_title
        self.current_company_name = company_name
        self.strict = False
        self.unanswered = []

        # Refuse to start without a real resume: never submit an application without one
        if not resume_path or not Path(resume_path).exists():
            master_pdf = DATA_DIR / "uploaded_resume.pdf"
            if master_pdf.exists():
                resume_path = str(master_pdf)
            else:
                return FormFillResult(
                    status="ERROR",
                    thread_id=tid,
                    job_title=job_title,
                    company_name=company_name,
                    error_message="No resume PDF found. Upload your resume in the Profile tab first.",
                )

        all_filled: List[FieldMatchResult] = []
        steps_count = 0

        session_dir = DATA_DIR / "browser_session"
        if "indeed.com" in target_url_or_path.lower():
            session_dir = DATA_DIR / "indeed_session"
        session_dir.mkdir(parents=True, exist_ok=True)
        sanitize_session_preferences(session_dir)

        with sync_playwright() as p:
            launch_args = list(get_stealth_chromium_args())
            launch_args.extend(["--no-first-run", "--no-default-browser-check"])
            launch_kwargs = {
                "user_data_dir": str(session_dir),
                "headless": self.headless,
                "channel": "chrome",
                "args": launch_args,
                "viewport": {"width": 1280, "height": 800},
                "user_agent": DEFAULT_USER_AGENT,
                "locale": "en-US",
                "timezone_id": "Asia/Kolkata",
                "ignore_https_errors": True,
            }
            try:
                context = p.chromium.launch_persistent_context(**launch_kwargs)
            except Exception:
                del launch_kwargs["channel"]
                context = p.chromium.launch_persistent_context(**launch_kwargs)

            context.add_init_script(build_stealth_js())
            page = context.pages[0] if context.pages else context.new_page()

            # Specialized handler for live Naukri applications
            if "naukri.com" in target_url_or_path.lower():
                return self._apply_naukri_live(
                    page=page,
                    context=context,
                    target_url=target_url_or_path,
                    job_title=job_title,
                    company_name=company_name,
                    tid=tid,
                    snapshot_file=snapshot_file,
                    confirmed_snapshot_file=confirmed_snapshot_file,
                    auto_submit=auto_submit,
                )

            # Specialized handler for live Indeed applications
            if "indeed.com" in target_url_or_path.lower():
                return self._apply_indeed_live(
                    page=page,
                    context=context,
                    target_url=target_url_or_path,
                    job_title=job_title,
                    company_name=company_name,
                    resume_path=resume_path,
                    tid=tid,
                    snapshot_file=snapshot_file,
                    confirmed_snapshot_file=confirmed_snapshot_file,
                    auto_submit=auto_submit,
                )

            # Format URL or local file for generic forms
            if target_url_or_path.startswith("http://") or target_url_or_path.startswith("https://"):
                try:
                    page.goto(target_url_or_path, timeout=30000, wait_until="domcontentloaded")
                except Exception as nav_err:
                    logger.error(f"Live portal navigation failed: {nav_err}")
                    context.close()
                    return FormFillResult(
                        status="NAVIGATION_FAILED",
                        thread_id=tid,
                        job_title=job_title,
                        company_name=company_name,
                        error_message=f"Live portal navigation failed: {nav_err}"
                    )
            else:
                local_file = Path(target_url_or_path).resolve()
                if not local_file.exists():
                    context.close()
                    return FormFillResult(
                        status="ERROR",
                        thread_id=tid,
                        job_title=job_title,
                        company_name=company_name,
                        error_message=f"Application target not found: {target_url_or_path}",
                    )
                page.goto(f"file:///{str(local_file).replace(os.sep, '/')}", wait_until="load")

            # Check if initial page triggered Cloudflare / CAPTCHA challenge
            initial_challenge = check_bot_challenge(page)
            if initial_challenge:
                logger.warning(f"[{tid}] Anti-bot challenge detected on entry: {initial_challenge}")
                context.close()
                return FormFillResult(
                    status="BOT_CHALLENGE",
                    thread_id=tid,
                    job_title=job_title,
                    company_name=company_name,
                    error_message=f"Bot Challenge Encountered: {initial_challenge}. Manual verification required.",
                    filled_fields=all_filled,
                    steps_traversed=0
                )

            max_steps = 10
            is_submit_ready = False

            while steps_count < max_steps:
                steps_count += 1
                logger.info(f"[{tid}] Processing Application Step {steps_count}...")

                # 1. Fill fields in current step
                filled_step = self.fill_visible_step(page, resume_path=resume_path)
                all_filled.extend(filled_step)

                # 2. Advance to next step
                advanced, on_submit_step = self.find_and_click_next(page)

                # Check if step transition triggered an anti-bot challenge
                step_challenge = check_bot_challenge(page)
                if step_challenge:
                    logger.warning(f"[{tid}] Anti-bot challenge detected at step {steps_count}: {step_challenge}")
                    context.close()
                    return FormFillResult(
                        status="BOT_CHALLENGE",
                        thread_id=tid,
                        job_title=job_title,
                        company_name=company_name,
                        error_message=f"Bot Challenge Encountered at step {steps_count}: {step_challenge}",
                        filled_fields=all_filled,
                        steps_traversed=steps_count
                    )

                if on_submit_step:
                    is_submit_ready = True
                    break

                if not advanced:
                    # No next button found; reached end of form
                    is_submit_ready = True
                    break

            # Reached Review Gateway Step
            logger.info(f"[{tid}] Reached Application Review Screen after {steps_count} steps.")

            if not auto_submit:
                # Assisted Mode: Capture review snapshot and pause at review gateway
                try:
                    page.screenshot(path=str(snapshot_file), full_page=False)
                except Exception:
                    pass
                context.close()
                return FormFillResult(
                    status="READY_FOR_REVIEW",
                    thread_id=tid,
                    job_title=job_title,
                    company_name=company_name,
                    snapshot_path=str(snapshot_file),
                    filled_fields=all_filled,
                    steps_traversed=steps_count
                )
            else:
                # Autonomous / Resumed Submission
                if self.unanswered:
                    unique_questions = list(dict.fromkeys(self.unanswered))
                    logger.warning(f"[{tid}] Unverified questions; submission stopped: {unique_questions}")
                    context.close()
                    return FormFillResult(
                        status="NEEDS_ANSWER",
                        thread_id=tid,
                        job_title=job_title,
                        company_name=company_name,
                        filled_fields=all_filled,
                        steps_traversed=steps_count,
                        error_message="Add verified answers for these questions in the Q&A bank, then retry: " + "; ".join(unique_questions),
                    )
                logger.info(f"[{tid}] Candidate approved. Submitting final application...")
                submit_selector = "button#btn-submit-application:visible, button:has-text('Submit application'):visible, button:has-text('Submit'):visible"
                submit_btn = page.query_selector(submit_selector)
                if not submit_btn:
                    # Never report SUBMITTED when no submit control was actually clicked
                    context.close()
                    return FormFillResult(
                        status="ERROR",
                        thread_id=tid,
                        job_title=job_title,
                        company_name=company_name,
                        filled_fields=all_filled,
                        steps_traversed=steps_count,
                        error_message="Submit button not found on the final review step. Nothing was submitted.",
                    )

                try:
                    HumanInteractionEngine.human_click_sync(page, submit_selector)
                except Exception:
                    submit_btn.click()
                page.wait_for_timeout(random.randint(500, 900))

                try:
                    page.screenshot(path=str(confirmed_snapshot_file), full_page=False)
                except Exception:
                    pass

                context.close()
                return FormFillResult(
                    status="SUBMITTED",
                    thread_id=tid,
                    job_title=job_title,
                    company_name=company_name,
                    confirmation_snapshot_path=str(confirmed_snapshot_file),
                    filled_fields=all_filled,
                    steps_traversed=steps_count
                )


def run_form_fill_pipeline(
    target_url_or_path: str,
    resume_path: Optional[str] = None,
    job_title: str = "Junior AI Engineer",
    company_name: str = "NextGen AI Labs",
    thread_id: Optional[str] = None,
    auto_submit: bool = False,
    headless: bool = True
) -> FormFillResult:
    """Convenience helper to run EasyApplyFiller."""
    filler = EasyApplyFiller(headless=headless)
    return filler.fill_and_stage_application(
        target_url_or_path=target_url_or_path,
        resume_path=resume_path,
        job_title=job_title,
        company_name=company_name,
        thread_id=thread_id,
        auto_submit=auto_submit
    )
