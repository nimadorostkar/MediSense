# MediSense — Demo Guide & Prompt Cheat‑Sheet

**Live:** https://medisense.nimadorostkar.com

MediSense is an AI clinical decision‑support demo for **dermatology**. You describe
a skin problem in plain language; it returns a **ranked differential diagnosis**,
the **recommended next test**, a **first‑line treatment** (with dosing, insurance
tier, and drug‑safety flags), and a natural **conversational explanation** — and
you can keep chatting to ask follow‑ups.

> Every answer is a *suggestion with its reasoning attached*. The licensed
> physician always confirms the final decision. **Not for real patient use.**

---

## 1. How the demo works (30‑second version)

1. Open **https://medisense.nimadorostkar.com** (use a private/incognito window the
   first time if your browser cached an old page).
2. Type a description of the skin lesion in the box → send.
3. Read the **AI answer** (top), the **ranked differential**, the **next best test**,
   and the **treatment card** (drugs, doses, safety).
4. **Ask a follow‑up** in the same chat — it remembers the case.

Two engines work together:
- **Grounded engine** (always on) — decides the diagnosis, probabilities, drugs,
  doses, and safety flags from a built‑in dermatology knowledge base.
- **Gemini AI** — writes the conversational wording and answers your follow‑ups.
  It *never* invents a diagnosis or dose; it only phrases what the engine found.

---

## 2. The formula for a good answer

Give it **three things**:

> **[what the lesion looks like] + [where on the body] + [how long]**
> *(optional: age, itch/pain, triggers like sun or contact)*

**Plain words work.** It understands everyday terms and maps them to clinical ones:

| You can say… | It understands… |
|---|---|
| silver / flaky / peeling | silvery scale |
| blackheads / whiteheads / pimples | comedones / papules / pustules |
| ring‑shaped / ringworm | annular |
| shiny bump with tiny blood vessels | pearly papule, telangiectasia |
| golden crusty sores | honey‑coloured crusts |
| a mole with uneven edges / colours | asymmetry, irregular border |

**Chinese works too** — e.g. `脸上有黑头白头和脓疱，油性皮肤`.

---

## 3. Cheat‑sheet — copy‑paste example prompts

Each of these produces a strong, correct answer.

### Inflammatory / eczema
- `red thick scaly patches with silvery flakes on my elbows and knees for 3 months`
- `itchy dry eczema in the elbow and knee creases of a child, keeps coming back`
- `red itchy blistery rash exactly where my watch strap touches my wrist`

### Infections
- `ring‑shaped itchy rash with a clear middle and scaly edge on the trunk`
- `kid with golden crusty sores around the mouth that are spreading`
- `painful cluster of blisters on the lip that keeps coming back in the same spot`
- `follicular pimples and pustules centred on hair follicles on the thighs`

### Acne / rosacea
- `blackheads, whiteheads and pus pimples on a teenager's oily face`
- `severe nodulocystic acne with deep painful lumps and scarring` *(picks a stronger treatment tier)*
- `persistent central facial redness with flushing and broken vessels, no blackheads`

### Hives
- `itchy hives and welts that come and go within a few hours`

### Skin‑cancer / do‑not‑miss (triggers a red‑flag banner)
- `a mole on my back that changed — uneven edges, two colours, and got bigger`
- `a slowly growing shiny pearly bump on the nose with tiny blood vessels that won't heal`
- `rapidly growing crusted ulcerated lump on the sun‑damaged lip of an elderly man`
- `painful mouth sores and flaccid blisters, skin peels when rubbed`

### Chinese examples
- `胳膊肘上有红色斑块，上面有银白色皮屑` *(psoriasis)*
- `身上有环形的癣，会脱皮和痒` *(tinea)*
- `嘴唇上长了一簇水泡，很痛，反复发作` *(herpes)*

---

## 4. Follow‑up questions you can ask (it keeps context)

After the first answer, just keep typing:

- `Why psoriasis and not eczema?`
- `Is any of that treatment unsafe in pregnancy?`
- `What's the dose again?`
- `What else should I check / what tests?`
- `What are the differentials I should rule out?`
- `Explain that more simply.`
- Or ask the same in **Chinese**.

**Example (real):**
> **You:** *Why psoriasis and not eczema? And is any of that treatment unsafe in pregnancy?*
> **MediSense:** *"Psoriasis often presents with silvery scales on well‑demarcated
> plaques on extensor surfaces like elbows and scalp… Eczema typically has less
> distinct borders. Regarding pregnancy, Tazarotene is contraindicated;
> Calcipotriol and Betamethasone are generally safer, but consult the
> obstetrician and pharmacist."*

---

## 5. Suggested 3‑minute live demo script

1. **Classic case →** `red thick scaly patches with silvery flakes on elbows and scalp for 3 months`
   *Point out:* ranked differential, the **treatment card** with doses + the
   **pregnancy contraindication** safety flag.
2. **Follow‑up →** `Is any of that treatment unsafe in pregnancy?`
   *Point out:* it answers in context, grounded in the safety data.
3. **Safety →** `a mole that changed — uneven edges, two colours, got bigger`
   *Point out:* the **red‑flag banner** → referral & biopsy (Melanoma).
4. **Bilingual →** `脸上有黑头白头和脓疱，油性皮肤`
   *Point out:* full Chinese answer (寻常痤疮 / acne).
5. **Safe‑by‑design →** `itchy red rash` (too vague)
   *Point out:* it **asks for morphology/location/duration** instead of guessing.

---

## 6. What to expect (and the honest limits)

- **Scope:** ~25 dermatology conditions (inflammatory, infections, acne/rosacea,
  pigmented lesions & skin cancers, bullous, drug eruptions). Best for skin cases.
- **Vague input** → it asks for more detail rather than guessing a diagnosis.
- **Non‑skin input** (e.g. chest pain) is out of scope for the dermatology demo.
- **AI wording** may occasionally be unavailable for a moment if the free Gemini
  quota is hit — the diagnosis, doses, and safety still show (grounded text).
- Bilingual **English / 中文**.

---

## 7. One‑line summary to tell people

> "Describe a skin problem the way a patient would — *what it looks like, where,
> and for how long* — and MediSense gives you a ranked differential, the next test,
> a screened treatment, and answers your follow‑up questions. It assists; the
> doctor decides."
