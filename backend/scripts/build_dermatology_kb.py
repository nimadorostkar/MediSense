"""Build the normalized 300-condition dermatology knowledge base.

The existing bilingual core files are the only clinically curated source in
this repository.  This builder preserves their content verbatim while creating
normalized modules and a complete MVP disease catalog.  Diseases that have not
yet been clinically authored are catalog entries only: no diagnostic or
treatment content is fabricated for them.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUT_DIR = DATA_DIR / "dermatology"
EN_FILE = DATA_DIR / "dermatology_core_data_EN.json"

VERSION = "2.0.0"
BUILD_DATE = "2026-07-23"

# Exact MVP allocation: 300 unique disorders across the requested categories.
# Keep this list clinical-name only; clinical assertions belong in the modules.
CATEGORIES: dict[str, list[str]] = {
    "pigmentary_disorders": [
        "Vitiligo", "Melasma", "Post-inflammatory hyperpigmentation",
        "Post-inflammatory hypopigmentation", "Oculocutaneous albinism",
        "Pityriasis alba", "Nevus depigmentosus", "Idiopathic guttate hypomelanosis",
        "Chemical leukoderma", "Ash leaf macules", "Lentigines", "Ephelides (freckles)",
        "Becker nevus", "Café-au-lait macules", "Exogenous ochronosis", "Nevus of Ota",
        "Nevus of Ito", "Acanthosis nigricans", "Lichen planus pigmentosus",
        "Erythema dyschromicum perstans",
    ],
    "eczema_and_dermatitis": [
        "Atopic dermatitis", "Allergic contact dermatitis",
        "Irritant contact dermatitis", "Seborrheic dermatitis", "Dyshidrotic eczema",
        "Nummular eczema", "Stasis dermatitis", "Hand eczema",
        "Lichen simplex chronicus (neurodermatitis)", "Asteatotic eczema",
        "Eyelid dermatitis", "Lip-licker dermatitis", "Photoallergic contact dermatitis",
        "Phototoxic contact dermatitis", "Phytophotodermatitis",
        "Airborne contact dermatitis", "Occupational dermatitis",
        "Juvenile plantar dermatosis", "Autoeczematization", "Systemic contact dermatitis",
        "Protein contact dermatitis", "Chronic actinic dermatitis", "Radiation dermatitis",
        "Intertriginous dermatitis", "Nipple eczema", "Ear canal eczema",
        "Peristomal dermatitis", "Incontinence-associated dermatitis",
        "Pityriasis amiantacea", "Exfoliative dermatitis",
    ],
    "papulosquamous_diseases": [
        "Plaque psoriasis", "Guttate psoriasis", "Inverse psoriasis",
        "Generalized pustular psoriasis", "Erythrodermic psoriasis",
        "Palmoplantar psoriasis", "Lichen planus", "Hypertrophic lichen planus",
        "Lichen nitidus", "Lichen striatus", "Pityriasis rosea",
        "Pityriasis rubra pilaris", "Small-plaque parapsoriasis",
        "Large-plaque parapsoriasis", "Pityriasis lichenoides chronica",
        "Pityriasis lichenoides et varioliformis acuta", "Secondary syphilis",
        "Reactive arthritis keratoderma",
    ],
    "autoimmune_bullous_diseases": [
        "Pemphigus vulgaris", "Pemphigus foliaceus", "Paraneoplastic pemphigus",
        "IgA pemphigus", "Bullous pemphigoid", "Mucous membrane pemphigoid",
        "Gestational pemphigoid", "Linear IgA bullous dermatosis",
        "Dermatitis herpetiformis", "Epidermolysis bullosa acquisita",
        "Bullous systemic lupus erythematosus", "Anti-p200 pemphigoid",
        "Lichen planus pemphigoides", "Pemphigoid nodularis",
        "Chronic bullous disease of childhood",
    ],
    "skin_infections": [
        "Impetigo", "Ecthyma", "Cellulitis", "Erysipelas", "Bacterial folliculitis",
        "Furuncle", "Carbuncle", "Necrotizing fasciitis", "Erythrasma",
        "Pitted keratolysis", "Trichomycosis axillaris", "Cutaneous anthrax",
        "Atypical mycobacterial skin infection", "Cutaneous tuberculosis",
        "Herpes simplex infection", "Varicella", "Herpes zoster",
        "Molluscum contagiosum", "Common wart", "Plantar wart", "Flat wart",
        "Condyloma acuminatum", "Orf", "Milker's nodule", "Hand-foot-and-mouth disease",
        "Mpox", "Measles", "Tinea corporis", "Tinea cruris", "Tinea pedis",
        "Tinea capitis", "Tinea barbae", "Tinea faciei", "Tinea manuum",
        "Onychomycosis", "Cutaneous candidiasis", "Pityriasis versicolor",
        "Majocchi granuloma", "Tinea incognito", "Sporotrichosis",
        "Chromoblastomycosis", "Mycetoma", "Scabies", "Pediculosis capitis",
        "Pediculosis corporis", "Pediculosis pubis", "Cutaneous larva migrans",
        "Cutaneous leishmaniasis", "Tungiasis", "Demodicosis",
    ],
    "acne_and_follicular_disorders": [
        "Acne vulgaris", "Acne conglobata", "Acne fulminans", "Neonatal acne",
        "Infantile acne", "Acne mechanica", "Acne cosmetica", "Steroid acne",
        "Drug-induced acneiform eruption", "Chloracne", "Rosacea",
        "Papulopustular rosacea", "Phymatous rosacea (rhinophyma)", "Ocular rosacea",
        "Perioral dermatitis", "Hidradenitis suppurativa",
        "Pseudofolliculitis barbae", "Keratosis pilaris", "Gram-negative folliculitis",
        "Malassezia folliculitis",
    ],
    "hair_disorders": [
        "Alopecia areata", "Androgenetic alopecia", "Telogen effluvium",
        "Anagen effluvium", "Trichotillomania", "Lichen planopilaris",
        "Frontal fibrosing alopecia", "Central centrifugal cicatricial alopecia",
        "Discoid lupus alopecia", "Folliculitis decalvans", "Dissecting cellulitis",
        "Traction alopecia", "Loose anagen syndrome", "Short anagen syndrome",
        "Trichorrhexis nodosa", "Monilethrix", "Pili torti", "Trichorrhexis invaginata",
        "Hypertrichosis", "Hirsutism",
    ],
    "nail_disorders": [
        "Paronychia", "Nail psoriasis", "Beau lines", "Koilonychia", "Onycholysis",
        "Digital clubbing", "Longitudinal melanonychia", "Onychomadesis",
        "Onychorrhexis", "Trachyonychia", "Pincer nail", "Ingrown toenail",
        "Green nail syndrome", "Median canaliform nail dystrophy", "Nail lichen planus",
    ],
    "benign_tumors": [
        "Seborrheic keratosis", "Dermatofibroma", "Epidermoid cyst", "Lipoma",
        "Cherry angioma", "Pyogenic granuloma", "Melanocytic nevus",
        "Acrochordon (skin tag)", "Congenital melanocytic nevus", "Blue nevus",
        "Spitz nevus", "Halo nevus", "Nevus sebaceous", "Pilomatricoma",
        "Trichoepithelioma", "Syringoma", "Sebaceous hyperplasia", "Angiokeratoma",
        "Neurofibroma", "Leiomyoma", "Glomus tumor", "Keloid",
    ],
    "skin_cancer": [
        "Basal cell carcinoma", "Cutaneous squamous cell carcinoma", "Melanoma",
        "Squamous cell carcinoma in situ (Bowen disease)", "Actinic keratosis",
        "Keratoacanthoma", "Merkel cell carcinoma", "Dermatofibrosarcoma protuberans",
        "Kaposi sarcoma", "Cutaneous T-cell lymphoma", "Mycosis fungoides",
        "Sézary syndrome", "Primary cutaneous anaplastic large-cell lymphoma",
        "Sebaceous carcinoma", "Microcystic adnexal carcinoma",
        "Extramammary Paget disease", "Angiosarcoma", "Acral lentiginous melanoma",
        "Lentigo maligna melanoma", "Nodular melanoma",
    ],
    "vascular_diseases": [
        "Infantile hemangioma", "Venous leg ulcer", "Cutaneous small-vessel vasculitis",
        "Livedo reticularis", "Purpura", "Port-wine stain", "Spider angioma",
        "Telangiectasia", "Venous malformation", "Lymphatic malformation",
        "Arteriovenous malformation", "Livedoid vasculopathy", "Stasis ulcer",
        "Calciphylaxis", "Cholesterol embolization syndrome",
    ],
    "connective_tissue_diseases": [
        "Acute cutaneous lupus erythematosus", "Subacute cutaneous lupus erythematosus",
        "Chronic cutaneous lupus erythematosus", "Dermatomyositis",
        "Systemic sclerosis", "Morphea", "Calcinosis cutis", "Mixed connective tissue disease",
        "Scleredema", "Scleromyxedema", "Eosinophilic fasciitis",
        "Graft-versus-host disease", "Rheumatoid nodule", "Granuloma annulare",
        "Necrobiosis lipoidica", "Palisaded neutrophilic granulomatous dermatitis",
        "Interstitial granulomatous dermatitis", "Relapsing polychondritis",
        "Behçet disease", "Antiphospholipid syndrome skin manifestations",
    ],
    "drug_reactions": [
        "Fixed drug eruption", "Stevens-Johnson syndrome",
        "Toxic epidermal necrolysis", "DRESS syndrome",
        "Acute generalized exanthematous pustulosis", "Morbilliform drug eruption",
        "Drug-induced urticaria", "Serum sickness-like reaction",
        "Drug-induced photosensitivity", "Drug-induced lupus erythematosus",
        "Drug-induced bullous pemphigoid", "Drug-induced pemphigus",
        "Anticoagulant-induced skin necrosis", "Heparin-induced skin necrosis",
        "Lichenoid drug eruption", "Acneiform drug eruption", "Drug-induced pigmentation",
        "Symmetrical drug-related intertriginous and flexural exanthema",
        "Generalized bullous fixed drug eruption", "Erythema multiforme",
    ],
    "pediatric_dermatology": [
        "Diaper dermatitis", "Erythema toxicum neonatorum", "Milia",
        "Transient neonatal pustular melanosis", "Nevus simplex", "Miliaria",
        "Cradle cap", "Aplasia cutis congenita", "Epidermolysis bullosa simplex",
        "Incontinentia pigmenti", "Ichthyosis vulgaris", "Harlequin ichthyosis",
        "Staphylococcal scalded skin syndrome", "Kawasaki disease",
        "Papular acrodermatitis of childhood",
    ],
}

LEGACY_SLUG_ALIASES = {
    "psoriasis": "plaque_psoriasis",
    "contact_dermatitis": "allergic_contact_dermatitis",
    "herpes_simplex": "herpes_simplex_infection",
    "tinea": "tinea_corporis",
    "folliculitis": "bacterial_folliculitis",
    "rhinophyma": "phymatous_rosacea_rhinophyma",
    "melanocytic_nevus": "melanocytic_nevus",
    "squamous_cell_carcinoma": "cutaneous_squamous_cell_carcinoma",
    "sjs_ten": "stevens_johnson_syndrome",
    "morbilliform_eruption": "morbilliform_drug_eruption",
    "urticaria_drug": "drug_induced_urticaria",
}

MODULES = [
    "symptoms", "physical_exam", "diagnostic_criteria", "differential_diagnosis",
    "laboratory_tests", "imaging", "treatment", "drug_database",
    "patient_education", "clinical_guidelines", "ai_rules",
]


def slugify(value: str) -> str:
    value = value.casefold().replace("é", "e").replace("ö", "o")
    value = re.sub(r"[^a-z0-9]+", "_", value).strip("_")
    return value


def dump(name: str, records: list[dict[str, Any]], description: str) -> None:
    payload = {
        "metadata": {
            "schema_version": VERSION,
            "generated": BUILD_DATE,
            "description": description,
            "record_count": len(records),
        },
        "records": records,
    }
    path = OUT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = sum(len(names) for names in CATEGORIES.values())
    if total != 300:
        raise ValueError(f"taxonomy must contain exactly 300 conditions, got {total}")

    disease_records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for category, names in CATEGORIES.items():
        for ordinal, name in enumerate(names, 1):
            slug = slugify(name)
            if slug in seen:
                raise ValueError(f"duplicate disease slug: {slug}")
            seen.add(slug)
            disease_records.append({
                "id": f"DER-{len(disease_records) + 1:03d}",
                "slug": slug,
                "name": name,
                "category": category,
                "category_ordinal": ordinal,
                "aliases": [],
                "icd10": None,
                "content_status": "catalog_only",
                "clinical_review": {
                    "status": "not_reviewed",
                    "reviewer": None,
                    "reviewed_at": None,
                },
            })

    by_slug = {record["slug"]: record for record in disease_records}
    with EN_FILE.open(encoding="utf-8") as handle:
        legacy = json.load(handle)["conditions"]

    modules: dict[str, list[dict[str, Any]]] = {name: [] for name in MODULES}
    drugs: dict[str, dict[str, Any]] = {}

    for legacy_slug, condition in legacy.items():
        if condition.get("category") == "diagnostic_tool":
            continue
        target_slug = LEGACY_SLUG_ALIASES.get(legacy_slug, legacy_slug)
        disease = by_slug.get(target_slug)
        if disease is None:
            raise ValueError(f"legacy condition has no catalog target: {legacy_slug}")
        disease_id = disease["id"]
        disease["icd10"] = condition.get("icd10")
        disease["content_status"] = "legacy_curated"
        disease["clinical_review"] = {
            "status": "migration_pending_revalidation",
            "reviewer": None,
            "reviewed_at": None,
        }
        if condition["name"].casefold() != disease["name"].casefold():
            disease["aliases"].append(condition["name"])

        modules["symptoms"].append({
            "id": f"SYM-{disease_id[4:]}",
            "disease_id": disease_id,
            "chief_complaint_template": condition.get("chief_complaint"),
            "severity_levels": condition.get("severity_levels", []),
            "source": "dermatology_core_data_EN.json",
        })
        modules["physical_exam"].append({
            "id": f"PEX-{disease_id[4:]}",
            "disease_id": disease_id,
            "key_findings": condition.get("key_physical_findings", []),
            "distribution": condition.get("distribution", []),
            "nail_findings": condition.get("nail_findings", []),
            "source": "dermatology_core_data_EN.json",
        })
        modules["diagnostic_criteria"].append({
            "id": f"DCR-{disease_id[4:]}",
            "disease_id": disease_id,
            "criteria": condition.get("diagnostic_criteria", []),
            "scoring_systems": condition.get("scoring", {}),
            "source": "dermatology_core_data_EN.json",
        })
        differentials = []
        for item in condition.get("differential_diagnosis", []):
            differentials.append({
                "candidate_slug": item.get("disease"),
                "differentiator": item.get("differentiator"),
                # A legacy free-text slug is deliberately not promoted to an FK.
                "candidate_disease_id": None,
            })
        modules["differential_diagnosis"].append({
            "id": f"DIF-{disease_id[4:]}",
            "disease_id": disease_id,
            "differentials": differentials,
            "source": "dermatology_core_data_EN.json",
        })
        modules["laboratory_tests"].append({
            "id": f"LAB-{disease_id[4:]}",
            "disease_id": disease_id,
            "diagnostic": condition.get("labs", []),
            "baseline": condition.get("labs_baseline", []),
            "before_systemic_therapy": condition.get("labs_before_systemic", []),
            "source": "dermatology_core_data_EN.json",
        })
        modules["imaging"].append({
            "id": f"IMG-{disease_id[4:]}",
            "disease_id": disease_id,
            "studies": condition.get("imaging", []),
            "source": "dermatology_core_data_EN.json",
        })

        treatment_tiers = []
        for tier, prescriptions in condition.get("prescriptions", {}).items():
            items = []
            for prescription in prescriptions:
                drug_name = prescription.get("drug")
                if not drug_name:
                    items.append({"non_drug_instruction": prescription})
                    continue
                drug_slug = slugify(drug_name)
                drug_id = f"DRUG-{hashlib.sha256(drug_slug.encode()).hexdigest()[:12].upper()}"
                drugs.setdefault(drug_slug, {
                    "id": drug_id,
                    "slug": drug_slug,
                    "name": drug_name,
                    "name_zh": prescription.get("drug_cn"),
                    "content_status": "legacy_curated",
                    "clinical_review": {"status": "migration_pending_revalidation"},
                    "source": "dermatology_core_data_EN.json",
                })
                details = {k: v for k, v in prescription.items() if k not in {"drug", "drug_cn"}}
                items.append({"drug_id": drug_id, **details})
            treatment_tiers.append({"tier": tier, "items": items})
        modules["treatment"].append({
            "id": f"TRT-{disease_id[4:]}",
            "disease_id": disease_id,
            "tiers": treatment_tiers,
            "follow_up": condition.get("follow_up", {}),
            "requires_physician_confirmation": True,
            "source": "dermatology_core_data_EN.json",
        })
        modules["patient_education"].append({
            "id": f"EDU-{disease_id[4:]}",
            "disease_id": disease_id,
            "points": condition.get("education", []),
            "source": "dermatology_core_data_EN.json",
        })
        modules["clinical_guidelines"].append({
            "id": f"GLN-{disease_id[4:]}",
            "disease_id": disease_id,
            "references": [],
            "status": "citation_required",
            "source": "dermatology_core_data_EN.json",
        })
        modules["ai_rules"].append({
            "id": f"AIR-{disease_id[4:]}",
            "disease_id": disease_id,
            "enabled": False,
            "rule_version": None,
            "reason": "Clinical revalidation and cited guidelines required before activation",
        })

    dump("disease", disease_records, "Canonical 300-condition dermatology MVP catalog")
    for module_name in MODULES:
        records = list(drugs.values()) if module_name == "drug_database" else modules[module_name]
        description = f"Normalized dermatology {module_name.replace('_', ' ')} records"
        dump(module_name, records, description)

    category_counts = Counter(record["category"] for record in disease_records)
    manifest = {
        "schema_version": VERSION,
        "disease_count": len(disease_records),
        "category_counts": dict(category_counts),
        "modules": [f"{name}.json" for name in ["disease", *MODULES]],
        "clinical_safety": {
            "catalog_only_records_are_not_actionable": True,
            "legacy_curated_records_require_revalidation": True,
            "ai_rules_default_enabled": False,
            "physician_confirmation_required": True,
        },
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
