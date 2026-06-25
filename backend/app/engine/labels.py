"""Bilingual condition labels (spec §15.2 localization, README bilingual feature).

Maps the knowledge-base condition names to Simplified Chinese for the zh UI.
In production this comes from the SNOMED CT / ICD-10-CM(CN) terminology service;
here it is a compact map covering the seed conditions.
"""
from __future__ import annotations

CONDITION_ZH = {
    "Community-acquired pneumonia": "社区获得性肺炎",
    "Acute bronchitis": "急性支气管炎",
    "Acute myocardial infarction": "急性心肌梗死",
    "Acute coronary syndrome": "急性冠脉综合征",
    "Stable angina": "稳定型心绞痛",
    "Migraine": "偏头痛",
    "Tension-type headache": "紧张性头痛",
    "Urinary tract infection (cystitis)": "尿路感染（膀胱炎）",
    "Acute pyelonephritis": "急性肾盂肾炎",
    "Acute appendicitis": "急性阑尾炎",
    "Acute gastroenteritis": "急性胃肠炎",
    "Acute asthma exacerbation": "急性哮喘发作",
    "Gastro-esophageal reflux disease": "胃食管反流病",
    "Pulmonary embolism": "肺栓塞",
    "Bacterial meningitis": "细菌性脑膜炎",
    "Sepsis": "脓毒症",
    "Acute ischemic stroke": "急性缺血性卒中",
}


def localize(condition: str, lang: str) -> str:
    if lang == "zh":
        return CONDITION_ZH.get(condition, condition)
    return condition
