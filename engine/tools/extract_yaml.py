#!/usr/bin/env python3
"""
extract_yaml.py — 从 STCC Markdown 文件批量抽取结构化 YAML
用法：python3 bin/extract_yaml.py
输出：knowledge/triage_protocols/{category}.yaml
"""

import re
import sys
import os
import yaml
from pathlib import Path

ROOT = Path(__file__).parent.parent
STCC_DIR = ROOT / "STCC"
OUT_DIR = ROOT / "knowledge" / "triage_protocols"

# 全量 225 文件 → category 映射
EXTRACT_MAP = {
    # ── abdominal_pain ──────────────────────────────────────
    "Abdominal_Pain_Adult.md":          "abdominal_pain",
    "Abdominal_Pain_Child.md":          "abdominal_pain",
    "Abdominal_Swelling.md":            "abdominal_pain",

    # ── fever ────────────────────────────────────────────────
    "Fever_Adult.md":                   "fever",
    "Fever_Child.md":                   "fever",
    "Sweating_Excessive.md":            "fever",

    # ── chest_and_heart ─────────────────────────────────────
    "Chest_Pain.md":                    "chest_and_heart",
    "Heart_Rate_Problems.md":           "chest_and_heart",
    "Congestive_Heart_Failure.md":      "chest_and_heart",
    "Hypertension.md":                  "chest_and_heart",
    "Hypotension.md":                   "chest_and_heart",
    "Shock_Suspected.md":               "chest_and_heart",
    "Chest_Trauma.md":                  "chest_and_heart",

    # ── respiratory ─────────────────────────────────────────
    "Breathing_Problems.md":            "respiratory",
    "Asthma.md":                        "respiratory",
    "Cough.md":                         "respiratory",
    "Wheezing.md":                      "respiratory",
    "Chronic_Obstructive_Pulmonary_Disease_COPD.md": "respiratory",
    "Choking.md":                       "respiratory",
    "Hyperventilation.md":              "respiratory",
    "Foreign_Body_Inhaled.md":          "respiratory",
    "Sleep_Apnea_Adult.md":             "respiratory",
    "Congestion.md":                    "respiratory",

    # ── head_and_neuro ──────────────────────────────────────
    "Head_Injury.md":                   "head_and_neuro",
    "Headache.md":                      "head_and_neuro",
    "Stroke_Suspected.md":              "head_and_neuro",
    "Altered_Mental_Status_AMS.md":     "head_and_neuro",
    "Confusion.md":                     "head_and_neuro",
    "Seizure.md":                       "head_and_neuro",
    "Seizure_Febrile.md":               "head_and_neuro",
    "Dizziness.md":                     "head_and_neuro",
    "Fainting.md":                      "head_and_neuro",
    "Numbness_and_Tingling.md":         "head_and_neuro",
    "Neurologic_Symptoms.md":           "head_and_neuro",
    "Speaking_Difficulty.md":           "head_and_neuro",
    "Weakness.md":                      "head_and_neuro",
    "Reye_Syndrome_Suspected.md":       "head_and_neuro",
    "Diabetes_Problems.md":             "head_and_neuro",

    # ── injury_trauma ───────────────────────────────────────
    "Burns_Thermal.md":                 "injury_trauma",
    "Burns_Chemical.md":                "injury_trauma",
    "Burns_Electrical.md":              "injury_trauma",
    "Laceration.md":                    "injury_trauma",
    "Ankle_Injury.md":                  "injury_trauma",
    "Abrasions.md":                     "injury_trauma",
    "BackNeck_Injury.md":               "injury_trauma",
    "Bleeding_Severe.md":               "injury_trauma",
    "Bone_Joint_and_Tissue_Injury.md":  "injury_trauma",
    "CastSplint_Problems.md":           "injury_trauma",
    "Electric_Injury.md":               "injury_trauma",
    "Extremity_Injury.md":              "injury_trauma",
    "Falls.md":                         "injury_trauma",
    "Immunization_Tetanus.md":          "injury_trauma",
    "Intravenous_Therapy_Problems.md":  "injury_trauma",
    "Postoperative_Problems.md":        "injury_trauma",
    "Puncture_Wound.md":                "injury_trauma",
    "Wound_Care:_Sutures_or_Staples.md": "injury_trauma",
    "Wound_Healing_and_Infection.md":   "injury_trauma",

    # ── infection_illness ───────────────────────────────────
    "Influenza.md":                     "infection_illness",
    "COVID-19.md":                      "infection_illness",
    "Chickenpox.md":                    "infection_illness",
    "Common_Cold_Symptoms.md":          "infection_illness",
    'Avian_Influenza_“Bird_Flu”_Exposure.md': "infection_illness",
    "Ebola:_Known_or_Suspected_Exposure.md":  "infection_illness",
    "Fatigue.md":                       "infection_illness",
    "Glands_Swollen_or_Tender.md":      "infection_illness",
    "Hepatitis.md":                     "infection_illness",
    "Impetigo.md":                      "infection_illness",
    "Mumps.md":                         "infection_illness",
    "Pertussis_Whooping_Cough.md":      "infection_illness",
    "Roseola.md":                       "infection_illness",
    "Rubella_German_Measles.md":        "infection_illness",
    "Rubeola_Measles.md":               "infection_illness",
    "Severe_Acute_Respiratory_Syndrome_SARS.md": "infection_illness",
    "Swine_Flu_H1N1_Virus_Exposure.md": "infection_illness",
    "West_Nile_Virus.md":               "infection_illness",
    "Zika_Virus.md":                    "infection_illness",

    # ── gastrointestinal ────────────────────────────────────
    "Diarrhea_Adult.md":                "gastrointestinal",
    "Diarrhea_Child.md":                "gastrointestinal",
    "Vomiting_Adult.md":                "gastrointestinal",
    "Vomiting_Child.md":                "gastrointestinal",
    "Indigestion.md":                   "gastrointestinal",
    "Constipation.md":                  "gastrointestinal",
    "Appetite_Loss_Adult.md":           "gastrointestinal",
    "Appetite_Loss_Child.md":           "gastrointestinal",
    "Dehydration.md":                   "gastrointestinal",
    "Feeding_Tube_Problems.md":         "gastrointestinal",
    "Foreign_Body_Rectum.md":           "gastrointestinal",
    "GasBelching.md":                   "gastrointestinal",
    "GasFlatulence.md":                 "gastrointestinal",
    "Heartburn.md":                     "gastrointestinal",
    "Hemorrhoids.md":                   "gastrointestinal",
    "Hiccups.md":                       "gastrointestinal",
    "Incontinence_Stool.md":            "gastrointestinal",
    "Jaundice.md":                      "gastrointestinal",
    "Ostomy_Problems.md":               "gastrointestinal",
    "Pinworms.md":                      "gastrointestinal",
    "Rectal_Bleeding.md":               "gastrointestinal",
    "Rectal_Problems.md":               "gastrointestinal",
    "Stools_Abnormal.md":               "gastrointestinal",
    "Swallowing_Difficulty.md":         "gastrointestinal",

    # ── urinary_genital ─────────────────────────────────────
    "Urination_Painful.md":             "urinary_genital",
    "Vaginal_Bleeding.md":              "urinary_genital",
    "Bed-Wetting.md":                   "urinary_genital",
    "Breast_Problems.md":               "urinary_genital",
    "Contraception_Emergency_EC.md":    "urinary_genital",
    "Foreign_Body_Vagina.md":           "urinary_genital",
    "Genital_Lesions.md":               "urinary_genital",
    "Genital_Problems_Male.md":         "urinary_genital",
    "Incontinence_Urine.md":            "urinary_genital",
    "Menstrual_Problems.md":            "urinary_genital",
    "Scrotal_Problems.md":              "urinary_genital",
    "Sexually_Transmitted_Disease_STD.md": "urinary_genital",
    "Urinary_CatheterNephrostomy_Tube_Problems.md": "urinary_genital",
    "Urination_Difficult.md":           "urinary_genital",
    "Urination_Excessive.md":           "urinary_genital",
    "Urine_Abnormal_Color.md":          "urinary_genital",
    "Vaginal_DischargePainItching.md":  "urinary_genital",

    # ── skin_rash_wound ─────────────────────────────────────
    "Rash_Adult.md":                    "skin_rash_wound",
    "Hives.md":                         "skin_rash_wound",
    "Rash_Child.md":                    "skin_rash_wound",
    "Bruising.md":                      "skin_rash_wound",
    "Facial_Skin_Problems.md":          "skin_rash_wound",
    "Foreign_Body_Skin.md":             "skin_rash_wound",
    "Hair_Loss.md":                     "skin_rash_wound",
    "Itching.md":                       "skin_rash_wound",
    "Lice.md":                          "skin_rash_wound",
    "PiercingPocketing_Problems.md":    "skin_rash_wound",
    "Scabies.md":                       "skin_rash_wound",
    "Shingles:_Suspected_or_Exposure.md": "skin_rash_wound",
    "Skin_Lesions:_Lumps_Bumps_and_Sores.md": "skin_rash_wound",
    "Sunburn.md":                       "skin_rash_wound",
    "Tattoo_Problems.md":               "skin_rash_wound",

    # ── mental_health ───────────────────────────────────────
    "Suicide_Attempt_Threat.md":        "mental_health",
    "Depression.md":                    "mental_health",
    "Alcohol_Problems.md":              "mental_health",
    "Anxiety.md":                       "mental_health",
    "Child_Abuse.md":                   "mental_health",
    "Domestic_Abuse.md":                "mental_health",
    "Elder_Abuse.md":                   "mental_health",
    "Hospice_Problems.md":              "mental_health",
    "Insomnia.md":                      "mental_health",
    "Sexual_Assault.md":                "mental_health",
    "Substance_Abuse_Use_or_Exposure.md": "mental_health",

    # ── allergic_reaction ───────────────────────────────────
    "Allergic_Reaction.md":             "allergic_reaction",
    "Food_Allergy_Known_or_Suspected.md": "allergic_reaction",
    "Hay_Fever_Problems.md":            "allergic_reaction",
    "Immunization_Reactions.md":        "allergic_reaction",

    # ── ear_eye_nose ────────────────────────────────────────
    "Earache_Drainage.md":              "ear_eye_nose",
    "Eye_Problems.md":                  "ear_eye_nose",
    "Bad_Breath.md":                    "ear_eye_nose",
    "Contact_Lens_Problems.md":         "ear_eye_nose",
    "Ear_Injury_Foreign_Body.md":       "ear_eye_nose",
    "Ear_Ringing.md":                   "ear_eye_nose",
    "Eye_Injury.md":                    "ear_eye_nose",
    "Facial_Problems.md":               "ear_eye_nose",
    "Foreign_Body_Eye.md":              "ear_eye_nose",
    "Foreign_Body_Nose.md":             "ear_eye_nose",
    "Hearing_Loss.md":                  "ear_eye_nose",
    "Hoarseness.md":                    "ear_eye_nose",
    "Mouth_Problems.md":                "ear_eye_nose",
    "Nose_Injury.md":                   "ear_eye_nose",
    "Nosebleed.md":                     "ear_eye_nose",
    "Pinkeye.md":                       "ear_eye_nose",
    "Sinus_Problems.md":                "ear_eye_nose",
    "Sore_Throat.md":                   "ear_eye_nose",
    "Stye.md":                          "ear_eye_nose",
    "Tongue_Problems.md":               "ear_eye_nose",
    "Tooth_Injury.md":                  "ear_eye_nose",
    "Toothache.md":                     "ear_eye_nose",
    "Vision_Problems.md":               "ear_eye_nose",

    # ── pain_muscle_joint ───────────────────────────────────
    "Back_Pain.md":                     "pain_muscle_joint",
    "Ankle_Problems.md":                "pain_muscle_joint",
    "Arm_or_Hand_Problems.md":          "pain_muscle_joint",
    "Arthritis_Problems.md":            "pain_muscle_joint",
    "Finger_and_Toe_Problems.md":       "pain_muscle_joint",
    "Foot_Problems.md":                 "pain_muscle_joint",
    "HandWrist_Problems.md":            "pain_muscle_joint",
    "Hip_PainInjury.md":               "pain_muscle_joint",
    "Jaw_Pain.md":                      "pain_muscle_joint",
    "Joint_PainSwelling.md":            "pain_muscle_joint",
    "Knee_PainSwellingInjury.md":       "pain_muscle_joint",
    "Leg_PainSwelling.md":              "pain_muscle_joint",
    "Muscle_Cramps.md":                 "pain_muscle_joint",
    "Neck_Pain.md":                     "pain_muscle_joint",
    "Shoulder_PainInjury.md":           "pain_muscle_joint",
    "Sickle_Cell_Disease_Problems.md":  "pain_muscle_joint",
    "Swelling.md":                      "pain_muscle_joint",

    # ── pediatric_specific ──────────────────────────────────
    "Newborn_Problems.md":              "pediatric_specific",
    "Breastfeeding_Problems.md":        "pediatric_specific",
    "Circumcision_Care.md":             "pediatric_specific",
    "Croup.md":                         "pediatric_specific",
    "Crying_Excessive_in_Infants.md":   "pediatric_specific",
    "Diaper_Rash.md":                   "pediatric_specific",
    "Sleep_Apnea_Infant.md":            "pediatric_specific",
    "Spitting_Up_Infant.md":            "pediatric_specific",
    "Teething.md":                      "pediatric_specific",
    "Umbilical_Cord_Care.md":           "pediatric_specific",

    # ── toxin_exposure ──────────────────────────────────────
    "Poisoning_Suspected.md":           "toxin_exposure",
    "Food_Poisoning_Suspected.md":      "toxin_exposure",
    "BloodBody_Fluid_Exposure.md":      "toxin_exposure",
    "Foreign_Body_Swallowing_of.md":    "toxin_exposure",
    "HIV_Exposure.md":                  "toxin_exposure",
    "Overdose.md":                      "toxin_exposure",

    # ── environmental_condition ─────────────────────────────
    "Heat_Exposure_Problems.md":        "environmental_condition",
    "Bee_Stings.md":                    "environmental_condition",
    "Bedbug_Exposure_or_Concerns.md":   "environmental_condition",
    "Bites_AnimalHuman.md":             "environmental_condition",
    "Bites_Insect.md":                  "environmental_condition",
    "Bites_Marine_Animal.md":           "environmental_condition",
    "Bites_Snake.md":                   "environmental_condition",
    "Bites_Tick.md":                    "environmental_condition",
    "Cold_Exposure_Problems.md":        "environmental_condition",
    "Drowning_Near_Drowning.md":        "environmental_condition",
    "Frostbite.md":                     "environmental_condition",
    "Sunburn.md":                       "environmental_condition",

    # ── pregnancy ───────────────────────────────────────────
    "Pregnancy_Suspected_Labor.md":     "pregnancy",
    "Pregnancy_Vaginal_Bleeding.md":    "pregnancy",
    "Postpartum_Problems.md":           "pregnancy",
    "Pregnancy_Cold_Symptoms.md":       "pregnancy",
    "Pregnancy_Fetal_Movement_Problems.md": "pregnancy",
    "Pregnancy_Hypertension.md":        "pregnancy",
    "Pregnancy_Leaking_Vaginal_Fluid.md": "pregnancy",
    "Pregnancy_Nausea_and_Vomiting.md": "pregnancy",
    "Pregnancy_Problems.md":            "pregnancy",
    "Pregnancy_Suspected_Labor_36_Weeks.md": "pregnancy",
    "Pregnancy_Urination_Problems.md":  "pregnancy",
}


def clean_bullets(lines):
    results = []
    for line in lines:
        line = line.strip()
        if line.startswith("●"):
            text = line[1:].strip()
            if text and len(text) > 2:
                results.append(text)
        elif line.startswith("- ") and len(line) > 3:
            text = line[2:].strip()
            if text and len(text) > 2:
                results.append(text)
    return results


def extract_action(text):
    patterns = [
        r'[是存在不存在]+\s*[""\'\'「」](.+?)[""\'\'「」]',
        r'[是存在]+\s*[""\'\'「」](.+)',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip().rstrip('"\'」"\'')
    return text.strip()


def parse_stcc_file(filepath):
    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines()

    result = {
        "topic_zh": "",
        "topic_en": filepath.stem.replace("_", " "),
        "source_file": f"STCC/{filepath.name}",
        "key_questions": [],
        "triage_levels": {
            "A": {"criteria": [], "action": "立即呼叫救护车（120）"},
            "B": {"criteria": [], "action": "立即前往急诊室"},
            "C": {"criteria": [], "action": "当天内联系医生/诊所"},
            "D": {"criteria": [], "action": "居家观察，按家庭护理指导"},
        },
        "home_care": [],
        "callback_criteria": [],
        "related_protocols": [],
    }

    for line in lines[:5]:
        if line.startswith("# "):
            result["topic_zh"] = line[2:].strip()
            break

    for line in lines:
        if "关键问题" in line:
            content = re.sub(r"关键问题[：:＊\s]*", "", line).strip()
            if content:
                result["key_questions"] = [
                    q.strip()
                    for q in re.split(r"[，,、；;]+", content)
                    if q.strip() and len(q.strip()) > 1
                ]
            break

    for line in lines:
        if "其他需要考虑" in line or "考虑的其他协议" in line or "其他需考虑" in line:
            names = re.findall(r"[一-鿿／/·\w]+(?=（\d)", line)
            result["related_protocols"] = [n.strip() for n in names if len(n.strip()) > 1]
            break

    in_assessment = False
    current_level = None
    current_criteria = []
    home_care_lines = []
    callback_lines = []
    in_home_care = False
    in_callback = False
    in_emergency = False
    emergency_lines = []

    for line in lines:
        stripped = line.strip()

        if re.match(r"^##\s*(评估|分级)", stripped):
            in_assessment = True
            in_home_care = False
            in_callback = False
            continue

        if re.match(r"^##\s*(家庭护理|居家护理|家居护理)", stripped):
            in_assessment = False
            in_home_care = True
            in_callback = False
            in_emergency = False
            if current_level and current_criteria:
                result["triage_levels"][current_level]["criteria"] = current_criteria[:]
            current_level = None
            current_criteria = []
            continue

        if re.match(r"^##\s*(如出现|出现以下|如果出现|请联系|如果发生)", stripped):
            if "立即" in stripped or "紧急" in stripped:
                in_emergency = True
                in_callback = False
                in_home_care = False
                in_assessment = False
            else:
                in_callback = True
                in_emergency = False
                in_home_care = False
                in_assessment = False
            if current_level and current_criteria:
                result["triage_levels"][current_level]["criteria"] = current_criteria[:]
            current_level = None
            current_criteria = []
            continue

        if stripped.startswith("##"):
            in_assessment = False
            in_home_care = False
            in_callback = False
            in_emergency = False
            if current_level and current_criteria:
                result["triage_levels"][current_level]["criteria"] = current_criteria[:]
            current_level = None
            current_criteria = []
            continue

        if in_assessment:
            level_match = re.match(r"^([ABCD])\.\s", stripped)
            if level_match:
                if current_level and current_criteria:
                    result["triage_levels"][current_level]["criteria"] = current_criteria[:]
                current_level = level_match.group(1)
                current_criteria = []
                continue

            if current_level:
                if re.search(r'[是存在否不存在]+\s*[""\'\'「」]', stripped) or \
                   re.search(r'[是否存在]+\s+"', stripped):
                    action = extract_action(stripped)
                    if action and len(action) > 2:
                        result["triage_levels"][current_level]["action"] = action
                    continue

                if re.match(r"^[否不存在↓→]+", stripped) and "转至" in stripped:
                    if current_criteria:
                        result["triage_levels"][current_level]["criteria"] = current_criteria[:]
                    continue

                if stripped.startswith("●") or stripped.startswith("- "):
                    text = stripped.lstrip("●- ").strip()
                    if text and len(text) > 2:
                        current_criteria.append(text)
                continue

        if in_home_care:
            home_care_lines.append(stripped)
            continue

        if in_callback:
            callback_lines.append(stripped)
            continue

        if in_emergency:
            emergency_lines.append(stripped)
            continue

    if current_level and current_criteria:
        result["triage_levels"][current_level]["criteria"] = current_criteria[:]

    result["home_care"] = clean_bullets(home_care_lines)
    cb = clean_bullets(callback_lines)
    em = clean_bullets(emergency_lines)
    result["callback_criteria"] = cb + [f"【立即急诊】{e}" for e in em]

    return result


def build_category_yaml(category, entries):
    protocols = []
    for idx, entry in enumerate(entries, 1):
        protocols.append({
            "id": f"{category}_{idx:03d}",
            "topic_zh": entry["topic_zh"],
            "topic_en": entry["topic_en"],
            "source_file": entry["source_file"],
            "key_questions": entry["key_questions"],
            "triage_levels": {
                level: {
                    "criteria": data["criteria"],
                    "action": data["action"],
                }
                for level, data in entry["triage_levels"].items()
                if data["criteria"] or level in ("A", "B")
            },
            "home_care": entry["home_care"],
            "callback_criteria": entry["callback_criteria"],
            "related_protocols": entry["related_protocols"],
        })
    return {"protocols": protocols}


def main():
    category_entries = {}
    errors = []
    files_found = 0

    for filename, category in EXTRACT_MAP.items():
        fp = STCC_DIR / filename
        if not fp.exists():
            print(f"  ⚠ 文件不存在：{filename}")
            errors.append(filename)
            continue
        files_found += 1
        try:
            entry = parse_stcc_file(fp)
            category_entries.setdefault(category, []).append(entry)
            print(f"  ✓ {filename} → {category} ({entry['topic_zh']})")
        except Exception as e:
            print(f"  ✗ {filename}: {e}")
            errors.append(filename)

    print(f"\n已处理 {files_found} 份文件，{len(errors)} 份失败")

    for category, entries in category_entries.items():
        out_path = OUT_DIR / f"{category}.yaml"
        data = build_category_yaml(category, entries)
        with open(out_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, default_flow_style=False,
                      sort_keys=False, width=120)
        print(f"  → {out_path} ({len(entries)} 条)")

    print(f"\n完成。共输出 {len(category_entries)} 个 category YAML。")
    if errors:
        print(f"失败文件：{errors}")


if __name__ == "__main__":
    main()
