"""Bundled scales and checklist templates (ADR 0026).

Only tools whose terms allow redistribution in an MIT app are bundled. The NHLBI Study
Quality Assessment Tools are U.S. Government works (17 U.S.C. § 105), so they are in the
public domain; the question texts below are verbatim from the NHLBI page (last updated
July 2021). Kitchenham's checklist, JBI's tools, RoB 2 and CASP are left out: their
terms are unclear or forbid commercial use or adaptation. Users can still paste the
questions of a tool they are licensed to use; the text stays in their library.

Question texts stay in the tool's own language (English); scale labels come in every UI
language, and the chosen language is copied into the review when a template is applied.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

Language = Literal["en", "tr"]


@dataclass(frozen=True)
class PresetOption:
    value: str
    labels: Mapping[Language, str]
    score: float | None


@dataclass(frozen=True)
class ScalePreset:
    key: str
    options: tuple[PresetOption, ...]


@dataclass(frozen=True)
class ChecklistTemplate:
    key: str
    title: str
    publisher: str
    # Study design the tool is meant for; the UI translates it.
    design: str
    version: str
    license: str
    source_url: str
    questions: tuple[str, ...]
    scale: str
    # A closing overall judgement with its own scale, if the tool has one.
    rating_question: str | None = None
    rating_scale: str | None = None


def _option(value: str, en: str, tr: str, score: float | None) -> PresetOption:
    return PresetOption(value=value, labels={"en": en, "tr": tr}, score=score)


_YES = _option("yes", "Yes", "Evet", 1.0)
_NO = _option("no", "No", "Hayır", 0.0)

SCALES: dict[str, ScalePreset] = {
    preset.key: preset
    for preset in (
        ScalePreset("yes_partly_no", (_YES, _option("partly", "Partly", "Kısmen", 0.5), _NO)),
        ScalePreset(
            "yes_no_unclear_na",
            (
                _YES,
                _NO,
                _option("unclear", "Unclear", "Belirsiz", None),
                _option("not_applicable", "Not applicable", "Uygulanamaz", None),
            ),
        ),
        ScalePreset(
            "risk_of_bias",
            (
                _option("low", "Low risk", "Düşük risk", None),
                _option("some_concerns", "Some concerns", "Bazı endişeler", None),
                _option("high", "High risk", "Yüksek risk", None),
            ),
        ),
        ScalePreset(
            "good_fair_poor",
            (
                _option("good", "Good", "İyi", None),
                _option("fair", "Fair", "Orta", None),
                _option("poor", "Poor", "Zayıf", None),
            ),
        ),
        ScalePreset(
            "nhlbi",
            (
                _YES,
                _NO,
                _option("cannot_determine", "Cannot determine", "Belirlenemiyor", None),
                _option("not_reported", "Not reported", "Raporlanmamış", None),
                _option("not_applicable", "Not applicable", "Uygulanamaz", None),
            ),
        ),
    )
}

_NHLBI = "National Heart, Lung, and Blood Institute (NHLBI)"
_NHLBI_URL = "https://www.nhlbi.nih.gov/health-topics/study-quality-assessment-tools"
_NHLBI_LICENSE = "Public domain (U.S. Government work, 17 U.S.C. § 105)"
_NHLBI_VERSION = "2021-07"
_NHLBI_RATING = "Quality rating (Good, Fair, or Poor)"


def _nhlbi(key: str, title: str, design: str, questions: tuple[str, ...]) -> ChecklistTemplate:
    return ChecklistTemplate(
        key=key,
        title=title,
        publisher=_NHLBI,
        design=design,
        version=_NHLBI_VERSION,
        license=_NHLBI_LICENSE,
        source_url=_NHLBI_URL,
        questions=questions,
        scale="nhlbi",
        rating_question=_NHLBI_RATING,
        rating_scale="good_fair_poor",
    )


TEMPLATES: dict[str, ChecklistTemplate] = {
    template.key: template
    for template in (
        _nhlbi(
            "nhlbi_controlled_intervention",
            "Quality Assessment of Controlled Intervention Studies",
            "controlled_intervention",
            (
                "Was the study described as randomized, a randomized trial, a randomized "
                "clinical trial, or an RCT?",
                "Was the method of randomization adequate (i.e., use of randomly generated "
                "assignment)?",
                "Was the treatment allocation concealed (so that assignments could not be "
                "predicted)?",
                "Were study participants and providers blinded to treatment group assignment?",
                "Were the people assessing the outcomes blinded to the participants' group "
                "assignments?",
                "Were the groups similar at baseline on important characteristics that could "
                "affect outcomes (e.g., demographics, risk factors, co-morbid conditions)?",
                "Was the overall drop-out rate from the study at endpoint 20% or lower of the "
                "number allocated to treatment?",
                "Was the differential drop-out rate (between treatment groups) at endpoint 15 "
                "percentage points or lower?",
                "Was there high adherence to the intervention protocols for each treatment group?",
                "Were other interventions avoided or similar in the groups (e.g., similar "
                "background treatments)?",
                "Were outcomes assessed using valid and reliable measures, implemented "
                "consistently across all study participants?",
                "Did the authors report that the sample size was sufficiently large to be able "
                "to detect a difference in the main outcome between groups with at least 80% "
                "power?",
                "Were outcomes reported or subgroups analyzed prespecified (i.e., identified "
                "before analyses were conducted)?",
                "Were all randomized participants analyzed in the group to which they were "
                "originally assigned, i.e., did they use an intention-to-treat analysis?",
            ),
        ),
        _nhlbi(
            "nhlbi_systematic_review",
            "Quality Assessment of Systematic Reviews and Meta-Analyses",
            "systematic_review",
            (
                "Is the review based on a focused question that is adequately formulated and "
                "described?",
                "Were eligibility criteria for included and excluded studies predefined and "
                "specified?",
                "Did the literature search strategy use a comprehensive, systematic approach?",
                "Were titles, abstracts, and full-text articles dually and independently "
                "reviewed for inclusion and exclusion to minimize bias?",
                "Was the quality of each included study rated independently by two or more "
                "reviewers using a standard method to appraise its internal validity?",
                "Were the included studies listed along with important characteristics and "
                "results of each study?",
                "Was publication bias assessed?",
                "Was heterogeneity assessed? (This question applies only to meta-analyses.)",
            ),
        ),
        _nhlbi(
            "nhlbi_cohort_cross_sectional",
            "Quality Assessment Tool for Observational Cohort and Cross-Sectional Studies",
            "cohort_cross_sectional",
            (
                "Was the research question or objective in this paper clearly stated?",
                "Was the study population clearly specified and defined?",
                "Was the participation rate of eligible persons at least 50%?",
                "Were all the subjects selected or recruited from the same or similar "
                "populations (including the same time period)? Were inclusion and exclusion "
                "criteria for being in the study prespecified and applied uniformly to all "
                "participants?",
                "Was a sample size justification, power description, or variance and effect "
                "estimates provided?",
                "For the analyses in this paper, were the exposure(s) of interest measured "
                "prior to the outcome(s) being measured?",
                "Was the timeframe sufficient so that one could reasonably expect to see an "
                "association between exposure and outcome if it existed?",
                "For exposures that can vary in amount or level, did the study examine "
                "different levels of the exposure as related to the outcome (e.g., categories "
                "of exposure, or exposure measured as continuous variable)?",
                "Were the exposure measures (independent variables) clearly defined, valid, "
                "reliable, and implemented consistently across all study participants?",
                "Was the exposure(s) assessed more than once over time?",
                "Were the outcome measures (dependent variables) clearly defined, valid, "
                "reliable, and implemented consistently across all study participants?",
                "Were the outcome assessors blinded to the exposure status of participants?",
                "Was loss to follow-up after baseline 20% or less?",
                "Were key potential confounding variables measured and adjusted statistically "
                "for their impact on the relationship between exposure(s) and outcome(s)?",
            ),
        ),
        _nhlbi(
            "nhlbi_case_control",
            "Quality Assessment of Case-Control Studies",
            "case_control",
            (
                "Was the research question or objective in this paper clearly stated and "
                "appropriate?",
                "Was the study population clearly specified and defined?",
                "Did the authors include a sample size justification?",
                "Were controls selected or recruited from the same or similar population that "
                "gave rise to the cases (including the same timeframe)?",
                "Were the definitions, inclusion and exclusion criteria, algorithms or "
                "processes used to identify or select cases and controls valid, reliable, and "
                "implemented consistently across all study participants?",
                "Were the cases clearly defined and differentiated from controls?",
                "If less than 100 percent of eligible cases and/or controls were selected for "
                "the study, were the cases and/or controls randomly selected from those "
                "eligible?",
                "Was there use of concurrent controls?",
                "Were the investigators able to confirm that the exposure/risk occurred prior "
                "to the development of the condition or event that defined a participant as a "
                "case?",
                "Were the measures of exposure/risk clearly defined, valid, reliable, and "
                "implemented consistently (including the same time period) across all study "
                "participants?",
                "Were the assessors of exposure/risk blinded to the case or control status of "
                "participants?",
                "Were key potential confounding variables measured and adjusted statistically "
                "in the analyses? If matching was used, did the investigators account for "
                "matching during study analysis?",
            ),
        ),
        _nhlbi(
            "nhlbi_before_after",
            "Quality Assessment Tool for Before-After (Pre-Post) Studies With No Control Group",
            "before_after",
            (
                "Was the study question or objective clearly stated?",
                "Were eligibility/selection criteria for the study population prespecified and "
                "clearly described?",
                "Were the participants in the study representative of those who would be "
                "eligible for the test/service/intervention in the general or clinical "
                "population of interest?",
                "Were all eligible participants that met the prespecified entry criteria enrolled?",
                "Was the sample size sufficiently large to provide confidence in the findings?",
                "Was the test/service/intervention clearly described and delivered "
                "consistently across the study population?",
                "Were the outcome measures prespecified, clearly defined, valid, reliable, and "
                "assessed consistently across all study participants?",
                "Were the people assessing the outcomes blinded to the participants' "
                "exposures/interventions?",
                "Was the loss to follow-up after baseline 20% or less? Were those lost to "
                "follow-up accounted for in the analysis?",
                "Did the statistical methods examine changes in outcome measures from before "
                "to after the intervention? Were statistical tests done that provided p values "
                "for the pre-to-post changes?",
                "Were outcome measures of interest taken multiple times before the "
                "intervention and multiple times after the intervention (i.e., did they use an "
                "interrupted time-series design)?",
                "If the intervention was conducted at a group level (e.g., a whole hospital, a "
                "community, etc.) did the statistical analysis take into account the use of "
                "individual-level data to determine effects at the group level?",
            ),
        ),
        _nhlbi(
            "nhlbi_case_series",
            "Quality Assessment Tool for Case Series Studies",
            "case_series",
            (
                "Was the study question or objective clearly stated?",
                "Was the study population clearly and fully described, including a case "
                "definition?",
                "Were the cases consecutive?",
                "Were the subjects comparable?",
                "Was the intervention clearly described?",
                "Were the outcome measures clearly defined, valid, reliable, and implemented "
                "consistently across all study participants?",
                "Was the length of follow-up adequate?",
                "Were the statistical methods well-described?",
                "Were the results well-described?",
            ),
        ),
    )
}
