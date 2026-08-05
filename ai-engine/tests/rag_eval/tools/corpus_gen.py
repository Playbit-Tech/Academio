# ruff: noqa: E501  # corpus data strings are intentionally long
"""Build + verify the RAG eval corpus and regenerate golden.jsonl refs (v2).

Strategy:
  - Docs are assembled from ANSWER SECTIONS placed at target chunk offsets,
    padded with filler so the home chunk (start//800) is exact.
  - Fragments are VERBATIM substrings of the corpus (judge stub matches).
  - expected_sources = the home chunks where fragments actually land
    (fragment-driven — no fragile keyword->doc mapping).
  - conftest's FakeEmbeddingClient is a deterministic keyword-hash vector so
    the dense leg carries real signal (constant vectors make RRF fragile).

Run (from the ai-engine repo root):
    uv run python tests/rag_eval/tools/corpus_gen.py

It rewrites tests/rag_eval/golden.jsonl in place; the hermetic test
``test_golden_fragments_contained_in_home_chunk`` (test_rag_eval.py) guards
the corpus/golden alignment so regen and committed state never drift.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # ai-engine/
from app.documents.chunker import chunk_text

HERE = Path(__file__).resolve().parent.parent  # tests/rag_eval/
GOLDEN = HERE / "golden.jsonl"


# ------------------------------------------------------------ assembler -----
def build(sections: list[tuple[int, str]], fillers: list[str]) -> str:
    """Place each (target_chunk, text) section so it starts at >= 800*target,
    padding gaps with fillers (cycled). Returns the assembled doc."""
    parts: list[str] = []
    cursor = 0
    fi = 0
    for target, text in sections:
        target_off = target * 800
        while cursor < target_off:
            parts.append(fillers[fi % len(fillers)])
            fi += 1
            cursor += len(fillers[(fi - 1) % len(fillers)])
        parts.append(text)
        cursor += len(text)
    return "".join(parts)


# --------------------------------------------------------------- corpus -----
CORPUS: dict[str, str] = {}

# --- geography_nigeria: refs chunk0..2 ---
CORPUS["geography_nigeria"] = build(
    [
        (0, "Nigeria is a country in West Africa and the most populous nation on the African "
            "continent. It lies on the Gulf of Guinea and shares land borders with Benin to the "
            "west, Niger and Chad to the north, and Cameroon to the east. The federal capital city "
            "of Nigeria is Abuja. Abuja serves as the federal capital and is the seat of government, "
            "where the president and the National Assembly convene. Abuja was built in the centre "
            "of the country to bring together its many regions."),
        (1, "The longest river in Nigeria is the Niger River. It flows through the country from the "
            "northwest and empties into the Atlantic Ocean at the Niger Delta in the south. Nigeria "
            "is home to more than two hundred and fifty ethnic groups; the three major ethnic groups "
            "are the Hausa in the north, the Yoruba in the southwest, and the Igbo in the southeast. "
            "Each group speaks its own language and preserves its own cultural traditions."),
        (2, "Nigeria currently has thirty-six states plus the Federal Capital Territory. The official "
            "language is English, used in government, education and business, and the unit of "
            "currency is the Naira, issued by the Central Bank of Nigeria. The north is drier and "
            "largely savannah, while the south is green and forested, and the economy depends on "
            "agriculture, oil and a young population."),
    ],
    [
        "Nigeria's climate is tropical, with a rainy season that varies between the north and the "
        "south. The country produces significant quantities of cocoa, palm oil and groundnuts, and "
        "its cities include Lagos, Kano and Ibadan. The people of Nigeria celebrate many festivals "
        "and are known for music, film and literature. ",
        "The federal system of government divides power between the national government and the "
        "states. Elections are held regularly, and the country has a strong tradition of civil "
        "society. Roads, railways and airports connect the major cities, and the population is "
        "young and growing quickly. ",
    ],
)

# --- math_geometry: refs chunk0..4 ---
CORPUS["math_geometry"] = build(
    [
        (0, "Geometry is the branch of mathematics that studies shapes, sizes, and the properties "
            "of space. It begins with simple figures such as points, lines, angles and polygons. "
            "The area of a triangle is one half of the base times the height, which we write as "
            "A equals one half b h. A triangle with a base of eight units and a height of five "
            "units has an area of twenty square units."),
        (1, "A circle is the set of points at a fixed distance from its centre. The circumference "
            "of a circle is pi times the diameter, equal to two pi times the radius. The value of "
            "pi rounded to two decimal places is three point one four. The diameter is twice the "
            "radius, so the two circumference formulas always produce the same length."),
        (2, "The Pythagorean theorem states that in a right triangle the sum of the squares of the "
            "two legs equals the square of the hypotenuse. For a right triangle with legs three "
            "and four, the hypotenuse is five. The sum of the interior angles of a triangle is "
            "one hundred eighty degrees, and the square root of 144 is twelve."),
        (3, "The volume of a rectangular prism is length times width times height, written V equals "
            "l w h. A box that is four long, three wide and two high has a volume of twenty-four "
            "cubic units. A rectangle with length five and width three has an area of fifteen "
            "square units, because the area of a rectangle is length times width."),
        (4, "A prime number is a whole number greater than one that is divisible only by one and "
            "itself. The number 11 is prime, but nine and fifteen are not prime: nine divides "
            "evenly by three, and fifteen divides evenly by three and five. Prime numbers are the "
            "building blocks of all whole numbers and are essential to modern cryptography."),
    ],
    [
        "Geometry is used in architecture, engineering, art and astronomy, and its rules are among "
        "the oldest recorded knowledge. Students learn to measure, to draw and to reason about "
        "shape, and these skills appear in daily life from cooking to construction. ",
        "Angles are measured in degrees, and parallel and perpendicular lines appear throughout "
        "geometry. Regular polygons have equal sides and equal angles, and their interior angle "
        "sums grow by one hundred eighty degrees with every additional side. These basics prepare "
        "students for trigonometry and calculus. ",
        "Mathematics is a language of precise statements and proofs. A theorem is a statement that "
        "has been proved, and an axiom is a statement accepted without proof. Mathematicians build "
        "careful chains of reasoning to show why results are true, and this rigour makes the "
        "subject reliable. ",
    ],
)

# --- lit_shakespeare: refs chunk0..4 ---
CORPUS["lit_shakespeare"] = build(
    [
        (0, "William Shakespeare was an English playwright and poet whose works are studied "
            "worldwide. He wrote the tragic play Romeo and Juliet, which is mainly set in the "
            "Italian city of Verona. Another great tragedy is Hamlet, whose tragic hero is Prince "
            "Hamlet, the prince of Denmark. Born in Stratford upon Avon, Shakespeare wrote "
            "tragedies, comedies and histories."),
        (1, "The two feuding families in Romeo and Juliet are the Montagues and the Capulets. The "
            "conflict between them drives the plot from the very first scene, and it forces Romeo "
            "and Juliet to meet in secret and finally to die. Their deaths reconcile the warring "
            "households."),
        (2, "The main theme explored through the lovers in Romeo and Juliet is the tension between "
            "fate versus free will, and the destructive power of hatred. The play is also a study "
            "of tragic love, showing how passion can overcome reason. The lovers are described as "
            "star crossed, meaning their destiny appears fixed by the stars."),
        (3, "Hamlet contains one of the most famous lines in literature, which begins the "
            "soliloquy about existence: To be, or not to be, that is the question. In this speech "
            "Hamlet weighs the pain of living against the fear of what may follow death, and the "
            "line has become proverbial across the English speaking world."),
        (4, "Shakespeare's poetry also includes The Rime of the Ancient Mariner, a narrative poem "
            "about guilt and redemption that explores the consequences of harming nature when the "
            "mariner kills an albatross and must atone for the act. The poem follows the mariner "
            "across a ghostly sea, where his crew dies and he alone survives to tell the story."),
    ],
    [
        "Shakespeare's plays explore love, power, ambition, jealousy and the human condition, and "
        "his characters have become archetypes of literature. Hundreds of words and phrases in "
        "daily use first appear in his work. ",
        "The plays were performed in the Globe Theatre in London, where audiences stood in the "
        "yard and richer patrons sat in galleries. Actors performed in daylight with minimal "
        "scenery, and the same company played both comedies and tragedies. ",
        "Scholars continue to debate Shakespeare's authorship, his sources and the original staging "
        "of his plays, but his influence on the English language is beyond dispute. For students, "
        "Shakespeare offers a gateway to poetry, theatre, history and philosophy all at once. ",
    ],
)

# --- science_biology: refs chunk0..4 ---
CORPUS["science_biology"] = build(
    [
        (0, "Biology is the scientific study of living organisms and the processes that sustain "
            "life. Photosynthesis is the process by which plants convert sunlight, carbon dioxide "
            "and water into glucose and oxygen. During photosynthesis, plants release oxygen into "
            "the air. This is why forests are sometimes called the lungs of the planet."),
        (1, "Inside plant cells, chloroplasts contain chlorophyll and capture light energy for "
            "photosynthesis. The mitochondria are known as the powerhouse of the cell because they "
            "produce energy from glucose in a process called cellular respiration. Chlorophyll is "
            "the green pigment that gives leaves their colour."),
        (2, "The human heart has four chambers: two atria and two ventricles. The atria receive "
            "blood and the ventricles pump it out to the lungs and the rest of the body. Red "
            "blood cells carry oxygen from the lungs to the rest of the body, using the protein "
            "haemoglobin that gives blood its red colour."),
        (3, "The roots of a plant absorb water and nutrients from the soil and anchor the plant in "
            "place. Root hairs increase the surface area for absorption. The stomata are small "
            "openings on a leaf surface that allow gas exchange, letting carbon dioxide in and "
            "oxygen out. Water travels up through the stem to the leaves."),
        (4, "An ecosystem is a community of living organisms interacting with each other and with "
            "their environment. An ecosystem includes plants, animals, fungi, bacteria, and the "
            "physical surroundings of soil, water, air and sunlight. Energy flows through the "
            "ecosystem in food chains, from producers to consumers to decomposers."),
    ],
    [
        "Biology covers everything from the smallest single celled microbe to the largest whale "
        "and the ecosystems they inhabit. Biologists ask how organisms are built, how they grow, "
        "how they obtain energy and how they reproduce. ",
        "The cell is the basic unit of life, and every living thing is made of cells that contain "
        "DNA carrying the instructions for building the organism. Cells divide to grow and repair "
        "tissues, and specialised cells form organs such as the brain, heart and lungs. ",
        "Understanding biology helps us protect health, grow food and conserve the natural world "
        "for future generations. Scientists study genetics, evolution and ecology, and their "
        "discoveries shape medicine, agriculture and conservation. ",
    ],
)

# --- science_chemistry: refs chunk0..2 ---
CORPUS["science_chemistry"] = build(
    [
        (0, "Chemistry is the study of matter and its transformations. At sea level the boiling "
            "point of water is one hundred degrees Celsius, equal to two hundred twelve degrees "
            "Fahrenheit. Water freezes at zero degrees Celsius, and these fixed points anchor the "
            "temperature scales used around the world."),
        (1, "The chemical formula for table salt is NaCl, also known as sodium chloride. Sodium "
            "and chlorine atoms join in a one to one ratio. The chemical symbol for gold is Au, "
            "taken from the Latin word aurum, and gold is prized for its lustre and its "
            "resistance to corrosion."),
        (2, "The pH scale measures how acidic or basic a solution is. A neutral solution has a pH "
            "value of seven, so we say neutral is pH 7; below seven is acidic and above seven is "
            "basic. Chemical reactions rearrange atoms but never create or destroy them, so the "
            "total mass of reactants equals the total mass of products."),
    ],
    [
        "Chemistry connects to biology, physics, medicine and industry, and chemists investigate "
        "how atoms combine into molecules and how substances change when they react. Matter is "
        "anything that has mass and takes up space. ",
        "The periodic table organises the elements by their atomic number and chemical behaviour, "
        "and it remains one of the most important tools in all of science. Laboratory work uses "
        "careful measurement, controlled reactions and safe handling of substances. ",
    ],
)

# --- science_physics: refs chunk0..2 ---
CORPUS["science_physics"] = build(
    [
        (0, "Physics is the study of matter, energy and their interactions. Newton's first law of "
            "motion states that an object stays at rest or continues in uniform motion unless "
            "acted upon by a net force. The formula relating force, mass and acceleration is "
            "F equals m a, which we also write as force equals mass times acceleration."),
        (1, "The acceleration due to gravity on Earth is approximately nine point eight meters per "
            "second squared. The speed of light in a vacuum is about three hundred thousand "
            "kilometers per second, which we write as three times ten to the eighth meters per "
            "second. Nothing travels faster than light."),
        (2, "Jupiter is the largest planet in our solar system, with a mass greater than all the "
            "other planets combined. Jupiter's strong gravity shapes the orbits of nearby "
            "asteroids and comets, and its Great Red Spot is a storm larger than Earth. Physics "
            "explains everything from the fall of an apple to the orbits of the planets."),
    ],
    [
        "Physicists use mathematics to describe nature and to predict the behaviour of systems, "
        "seeking the fundamental laws that govern everything from the smallest particle to the "
        "largest galaxy. Energy can change form but cannot be created or destroyed. ",
        "The law of inertia explains why a ball keeps rolling on a smooth surface until friction "
        "stops it, and a heavier object needs a larger force to reach the same acceleration as a "
        "lighter one. Classical mechanics, electricity and magnetism all rest on careful "
        "measurement and experiment. ",
    ],
)

# --- history_nigeria: refs chunk0..3 ---
CORPUS["history_nigeria"] = build(
    [
        (0, "Nigeria gained independence from Britain in the year 1960, which we say as nineteen "
            "sixty. October 1st is celebrated as Independence Day every year, marking the end of "
            "colonial rule and the birth of a new nation. Abubakar Tafawa Balewa became the first "
            "Prime Minister of Nigeria and led the federation in its early years."),
        (1, "The Nigerian Civil War was fought from 1967 to 1970, which we say as nineteen "
            "sixty-seven to nineteen seventy. The breakaway region was called the Republic of "
            "Biafra, and the conflict remains a significant part of Nigeria's history. The war "
            "began when the eastern region declared independence."),
        (2, "The largest state by area in Nigeria is Niger State, located in the north central "
            "part of the country. Its capital is Minna, and it takes its name from the Niger "
            "River which flows along part of its border. Geography and history together shaped "
            "the modern states of the Nigerian federation."),
        (3, "The national flag of Nigeria has three vertical bands of green, white and green, so "
            "it is often described as having vertical green-white green bands. The green color "
            "represents agriculture and the natural wealth of the country, while the white band "
            "symbolizes peace and unity. The national animal of Nigeria is the eagle, which "
            "symbolizes strength."),
    ],
    [
        "The road to independence involved decades of political activity, constitutional "
        "conferences and nationalist movements, and the new nation inherited a rich cultural "
        "heritage and enormous natural resources. ",
        "The eagle appears on the national coat of arms together with two white horses and a "
        "black shield, and the national motto is Unity and Faith, Peace and Progress. Historians "
        "study Nigerian history through oral traditions, archaeology and colonial records. ",
    ],
)

# --- geography_africa: refs chunk0..4 ---
CORPUS["geography_africa"] = build(
    [
        (0, "Africa is the second largest continent on Earth. The highest mountain in Africa is "
            "Mount Kilimanjaro, which rises in Tanzania. The Sahara Desert covers much of "
            "northern Africa and is the largest hot desert in the world. Africa is the cradle of "
            "humankind, rich in natural resources."),
        (1, "The longest river in Africa is the Nile, which flows north through several countries "
            "into the Mediterranean Sea. The Nile runs more than six thousand kilometers, and its "
            "valley has supported civilisation in Egypt and Sudan since ancient times."),
        (2, "The administrative capital of South Africa is Pretoria, one of three capitals of the "
            "country. Pretoria hosts the executive branch of government, while Cape Town hosts "
            "the parliament and Bloemfontein hosts the judiciary. South Africa is the most "
            "industrialised economy on the continent."),
        (3, "The tilt of the Earth's axis is the main cause of the seasons: as the Earth orbits "
            "the sun, different parts of the planet receive different amounts of sunlight. The "
            "Atlantic Ocean borders West African countries like Nigeria to the south, providing "
            "important trade routes and fisheries."),
        (4, "Meteorology is the study of weather and atmospheric conditions. Meteorologists "
            "measure temperature, pressure, humidity and wind, and they use satellites and "
            "computer models to forecast storms, droughts and rainfall. Weather shapes "
            "agriculture, transport and daily life across the continent."),
    ],
    [
        "Africa contains fifty-four countries and stretches from the Mediterranean in the north "
        "to the Cape of Good Hope in the south. Its landscapes range from deserts and savannahs "
        "to rainforests and high mountains. ",
        "The Sahara spans about nine million square kilometers, and its dunes, plateaus and oases "
        "stretch from the Atlantic coast to the Red Sea. The Indian Ocean washes the eastern "
        "coast, and the Atlantic coast is lined with ports, mangroves and fishing villages. ",
    ],
)

# --- lit_african: refs chunk0..1 ---
CORPUS["lit_african"] = build(
    [
        (0, "Chinua Achebe was a Nigerian novelist, poet and critic, widely regarded as the "
            "father of modern African literature. Things Fall Apart is his most famous novel, "
            "first published in 1958. The protagonist of Things Fall Apart is Okonkwo, a proud "
            "and ambitious warrior of the Igbo people."),
        (1, "The setting of Things Fall Apart is the late nineteenth century, mainly in the Igbo "
            "village of Umuofia. The village of Umuofia has its own customs, laws, festivals and "
            "council of elders, and Achebe describes daily life among the yam farmers, wrestlers, "
            "storytellers and priests who inhabit it."),
    ],
    [
        "Achebe wrote in English while drawing deeply on Igbo oral traditions, and his works are "
        "studied around the world. He wrote the novel in part to correct the distorted image of "
        "Africa found in earlier European fiction. ",
        "The novel explores themes of tradition and change, masculinity and fear, and the tragedy "
        "of a culture overtaken by forces it cannot control. For students of African literature, "
        "Things Fall Apart is an essential text. ",
    ],
)

# ---------------------------------------------------------------- QA pairs -----
GOLDEN_QA = [
    ("What is the capital city of Nigeria?",
     ["Abuja serves as the federal capital", "seat of government"]),
    ("Which river is the longest in Nigeria and where does it flow?",
     ["Niger River", "flows through the country", "empties into the Atlantic Ocean"]),
    ("Name three major ethnic groups in Nigeria.",
     ["Hausa", "Yoruba", "Igbo"]),
    ("What is the formula for the area of a triangle?",
     ["one half of the base times the height", "A equals one half b h"]),
    ("How do you compute the circumference of a circle?",
     ["pi times the diameter", "two pi times the radius"]),
    ("What does the Pythagorean theorem state for a right triangle?",
     ["sum of the squares of the two legs", "square of the hypotenuse"]),
    ("What is the value of pi rounded to two decimal places?",
     ["three point one four"]),
    ("Who wrote the play Romeo and Juliet?",
     ["William Shakespeare"]),
    ("In which city is Romeo and Juliet mainly set?",
     ["Verona", "Italian city"]),
    ("What are the two feuding families in Romeo and Juliet?",
     ["Montagues", "Capulets"]),
    ("What is the main theme explored through the lovers in Romeo and Juliet?",
     ["fate versus free will", "tragic love"]),
    ("Who is the tragic hero in Shakespeare's Hamlet?",
     ["Prince Hamlet", "the prince of Denmark"]),
    ("What famous line begins Hamlet's soliloquy about existence?",
     ["To be, or not to be, that is the question"]),
    ("What is photosynthesis?",
     ["plants convert sunlight", "carbon dioxide and water", "glucose and oxygen"]),
    ("Which gas do plants release during photosynthesis?",
     ["release oxygen"]),
    ("What role do chloroplasts play in a plant cell?",
     ["contain chlorophyll", "capture light energy"]),
    ("What is the powerhouse of the cell?",
     ["mitochondria"]),
    ("How many chambers does the human heart have?",
     ["four chambers", "two atria and two ventricles"]),
    ("What is the function of red blood cells?",
     ["carry oxygen"]),
    ("What is the boiling point of water at sea level?",
     ["one hundred degrees Celsius", "two hundred twelve degrees Fahrenheit"]),
    ("What is the chemical formula for table salt?",
     ["NaCl", "sodium chloride"]),
    ("What is the chemical symbol for gold?",
     ["chemical symbol for gold is Au"]),
    ("What is the pH value of a neutral solution?",
     ["pH value of seven", "neutral is pH 7"]),
    ("What is Newton's first law of motion?",
     ["stays at rest", "uniform motion unless acted upon by a net force"]),
    ("What is the formula that relates force, mass and acceleration?",
     ["F equals m a", "force equals mass times acceleration"]),
    ("What is the acceleration due to gravity on Earth?",
     ["nine point eight meters per second squared"]),
    ("What is the speed of light in a vacuum?",
     ["three hundred thousand kilometers per second", "three times ten to the eighth"]),
    ("In which year did Nigeria gain independence from Britain?",
     ["nineteen sixty"]),
    ("Who was Nigeria's first Prime Minister?",
     ["Abubakar Tafawa Balewa"]),
    ("What event is celebrated on October 1st in Nigeria?",
     ["Independence Day"]),
    ("When was the Nigerian Civil War fought?",
     ["nineteen sixty-seven to nineteen seventy"]),
    ("What was the name of the breakaway republic in the Nigerian Civil War?",
     ["Republic of Biafra"]),
    ("What is the largest state by area in Nigeria?",
     ["Niger State"]),
    ("What is the highest mountain in Africa?",
     ["Mount Kilimanjaro"]),
    ("Which desert covers much of northern Africa?",
     ["Sahara Desert"]),
    ("Which is the longest river in Africa?",
     ["longest river in Africa is the Nile"]),
    ("What is the capital of South Africa (administrative seat)?",
     ["administrative capital of South Africa is Pretoria"]),
    ("What is the official language of Nigeria?",
     ["official language is English"]),
    ("How many states does Nigeria currently have?",
     ["thirty-six states"]),
    ("What is the unit of currency in Nigeria?",
     ["unit of currency is the Naira"]),
    ("What is the name of the Nigerian national flag?",
     ["vertical green-white green bands"]),
    ("What does the green color on the Nigerian flag represent?",
     ["represents agriculture and the natural wealth", "natural wealth"]),
    ("Who is the author of Things Fall Apart?",
     ["Chinua Achebe"]),
    ("Who is the protagonist of Things Fall Apart?",
     ["Okonkwo"]),
    ("What is the setting of Things Fall Apart?",
     ["Igbo village of Umuofia"]),
    ("What is the main theme of the poem The Rime of the Ancient Mariner?",
     ["guilt and redemption", "consequences of harming nature"]),
    ("What is the value of the square root of 144?",
     ["square root of 144 is twelve"]),
    ("What is the sum of the interior angles of a triangle?",
     ["one hundred eighty degrees"]),
    ("What is the formula for the volume of a rectangular prism?",
     ["length times width times height"]),
    ("What is the area of a rectangle with length 5 and width 3?",
     ["fifteen square units"]),
    ("What is a prime number?",
     ["greater than one", "divisible only by one and itself"]),
    ("Which of these is prime: 9, 11, or 15?",
     ["The number 11 is prime"]),
    ("What is the main function of the roots of a plant?",
     ["absorb water and nutrients", "anchor the plant in place"]),
    ("What is the role of the stomata in a leaf?",
     ["allow gas exchange", "carbon dioxide in and oxygen out"]),
    ("What is an ecosystem?",
     ["community of living organisms",
      "interacting with each other and with their environment"]),
    ("What is the main cause of the seasons?",
     ["tilt of the Earth's axis"]),
    ("Which ocean borders Nigeria to the south?",
     ["Atlantic Ocean borders West African countries"]),
    ("What is the largest planet in our solar system?",
     ["largest planet in our solar system"]),
    ("What is the name given to the study of weather?",
     ["Meteorology is the study of weather"]),
    ("What is the national animal of Nigeria?",
     ["national animal of Nigeria is the eagle"]),
]


def find_doc_with(frag: str) -> str | None:
    """Return the corpus doc containing the fragment verbatim."""
    for doc_id, text in CORPUS.items():
        if frag.lower() in text.lower():
            return doc_id
    return None


def main() -> int:
    problems = 0
    for doc_id, text in CORPUS.items():
        n = len(chunk_text(text))
        print(f"{doc_id:<20} len={len(text):>5} chunks={n}")

    entries: list[dict] = []
    for q, frags in GOLDEN_QA:
        expected: set[str] = set()
        entry_docs: set[str] = set()
        for frag in frags:
            doc_id = find_doc_with(frag)
            if doc_id is None:
                print(f"  MISSING frag anywhere: {frag!r}  (q: {q[:60]})")
                problems += 1
                continue
            entry_docs.add(doc_id)
            start = CORPUS[doc_id].lower().find(frag.lower())
            home = start // 800
            expected.add(f"{doc_id}_chunk{home}")
        if len(entry_docs) > 1:
            print(f"  FRAGMENTS SPAN DOCS {sorted(entry_docs)}: {q[:60]}")
            problems += 1
        if not expected:
            problems += 1
            continue
        entries.append({
            "question": q,
            "expected_sources": sorted(expected, key=lambda r: int(r.rsplit("_chunk", 1)[1])),
            "expected_answer_fragments": frags,
        })

    print(f"\nentries: {len(entries)}/{len(GOLDEN_QA)}  problems={problems}")
    if problems == 0:
        with GOLDEN.open("w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
        print(f"wrote {GOLDEN}")
        c = Counter(r.rsplit("_chunk", 1)[0] for e in entries for r in e["expected_sources"])
        print("refs per doc:", dict(c))
        from collections import defaultdict
        bychunk = defaultdict(int)
        for e in entries:
            for r in e["expected_sources"]:
                bychunk[int(r.rsplit("_chunk", 1)[1])] += 1
        print("refs by chunk index:", dict(sorted(bychunk.items())))
    return 0 if problems == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
