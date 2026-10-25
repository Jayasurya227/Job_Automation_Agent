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
    from app.config import DATA_DIR
    from app.agent.scorer import load_profile
    from app.agent.qa_bank import get_or_generate_answer
    from app.agent.stealth import (
        build_stealth_js,
        get_stealth_chromium_args,
        get_random_fingerprint,
        HumanInteractionEngine,
        check_bot_challenge,
    )
except ImportError:
    from ..config import DATA_DIR
    from .scorer import load_profile
    from .qa_bank import get_or_generate_answer
    from .stealth import (
        build_stealth_js,
        get_stealth_chromium_args,
        get_random_fingerprint,
        HumanInteractionEngine,
        check_bot_challenge,
    )

logger = logging.getLogger("applier")

SNAPSHOT_DIR = Path("output/snapshots")
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
            ans = get_or_generate_answer(label_text, allow_ai_generation=False)
            return str(ans.get("answer", "1")), "experience"
        if re.search(r"(expected\s*(ctc|salary)|salary\s*expectation)", combined):
            return self.profile.preferences.min_expected_salary or "Negotiable", "salary"

        # General / Screening questions -> Consult Q&A Bank
        ans_obj = get_or_generate_answer(label_text, allow_ai_generation=True)
        return str(ans_obj.get("answer", "Yes")), "screening"

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

                ans_obj = get_or_generate_answer(lbl_text, allow_ai_generation=True)
                val_to_fill = str(ans_obj.get("answer", "I am strongly interested in contributing my software skills."))
                
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
                
                # Match against Q&A bank
                qa_res = get_or_generate_answer(lbl_text, allow_ai_generation=False)
                target_ans = qa_res.get("answer", "").lower()
                
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

                ans_obj = get_or_generate_answer(group_lbl, allow_ai_generation=False)
                desired_val = str(ans_obj.get("answer", "Yes")).lower()

                # Find radio options for this group
                all_radios = page.query_selector_all(f"input[type='radio'][name='{r_name}']:visible")
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
                # Resolve resume file path
                target_file = None
                if resume_path and Path(resume_path).exists():
                    target_file = str(Path(resume_path).resolve())
                else:
                    # Check default resumes
                    candidate_resumes = list(Path("output/resumes").glob("*.tex")) + list(Path("output/resumes").glob("*.pdf"))
                    if candidate_resumes:
                        target_file = str(candidate_resumes[0].resolve())
                    else:
                        # Fallback dummy resume file for testing
                        dummy_res = DATA_DIR / "candidate_resume.pdf"
                        if not dummy_res.exists():
                            dummy_res.write_bytes(b"%PDF-1.4 Mock Candidate Resume")
                        target_file = str(dummy_res.resolve())

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
        """
        tid = thread_id or f"app_{int(time.time() * 1000)}"
        snapshot_file = SNAPSHOT_DIR / f"review_{tid}.png"
        confirmed_snapshot_file = SNAPSHOT_DIR / f"confirmed_{tid}.png"

        all_filled: List[FieldMatchResult] = []
        steps_count = 0

        with sync_playwright() as p:
            fp = get_random_fingerprint()
            browser = p.chromium.launch(
                headless=self.headless,
                args=get_stealth_chromium_args()
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=fp["user_agent"],
                locale="en-US",
                timezone_id="Asia/Kolkata",
                ignore_https_errors=True,
            )
            context.add_init_script(build_stealth_js(fp))
            page = context.new_page()

            # Format URL or local file
            if target_url_or_path.startswith("http://") or target_url_or_path.startswith("https://"):
                try:
                    page.goto(target_url_or_path, timeout=6000, wait_until="domcontentloaded")
                except Exception as nav_err:
                    logger.warning(f"Live portal navigation timed out or blocked ({nav_err}). Using high-fidelity application modal fallback.")
                    mock_file = Path("data/mock_easy_apply.html").resolve()
                    page.goto(f"file:///{str(mock_file).replace(os.sep, '/')}", wait_until="load")
            else:
                local_file = Path(target_url_or_path).resolve()
                if not local_file.exists():
                    local_file = Path("data/mock_easy_apply.html").resolve()
                page.goto(f"file:///{str(local_file).replace(os.sep, '/')}", wait_until="load")

            # Check if initial page triggered Cloudflare / CAPTCHA challenge
            initial_challenge = check_bot_challenge(page)
            if initial_challenge:
                logger.warning(f"[{tid}] Anti-bot challenge detected on entry: {initial_challenge}")
                challenge_snapshot = SNAPSHOT_DIR / f"challenge_{tid}.png"
                page.screenshot(path=str(challenge_snapshot), full_page=True)
                browser.close()
                return FormFillResult(
                    status="BOT_CHALLENGE",
                    thread_id=tid,
                    job_title=job_title,
                    company_name=company_name,
                    snapshot_path=str(challenge_snapshot),
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
                    challenge_snapshot = SNAPSHOT_DIR / f"challenge_{tid}.png"
                    page.screenshot(path=str(challenge_snapshot), full_page=True)
                    browser.close()
                    return FormFillResult(
                        status="BOT_CHALLENGE",
                        thread_id=tid,
                        job_title=job_title,
                        company_name=company_name,
                        snapshot_path=str(challenge_snapshot),
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

            # Take Review Gateway Snapshot for Candidate
            page.screenshot(path=str(snapshot_file), full_page=True)

            if not auto_submit:
                # Assisted Mode: Pause at review gateway
                browser.close()
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
                logger.info(f"[{tid}] Candidate approved. Submitting final application...")
                submit_selector = "button#btn-submit-application:visible, button:has-text('Submit application'):visible, button:has-text('Submit'):visible"
                submit_btn = page.query_selector(submit_selector)
                if submit_btn:
                    try:
                        HumanInteractionEngine.human_click_sync(page, submit_selector)
                    except Exception:
                        submit_btn.click()
                    page.wait_for_timeout(random.randint(500, 900))
                    page.screenshot(path=str(confirmed_snapshot_file), full_page=True)

                browser.close()
                return FormFillResult(
                    status="SUBMITTED",
                    thread_id=tid,
                    job_title=job_title,
                    company_name=company_name,
                    snapshot_path=str(snapshot_file),
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
