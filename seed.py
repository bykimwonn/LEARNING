"""
BT LEARNING — demo seed data. Creates admin, teachers, school students,
an independent student, multiple classes, sample notes, past papers,
plus a realistic set of quiz attempts / weaknesses so the teacher's
Command Center, AI Intervention reports and leaderboard have content.
"""
import db
import ai_engine as ai
from werkzeug.security import generate_password_hash

MATH_NOTE = """Linear Equations: What They Are
A linear equation is an equation where the highest power of the variable is one. It describes a straight line when it is drawn on a graph. For example, the equation y equals two x plus three is a linear equation because x and y appear only to the first power.

Solving a Linear Equation
To solve a linear equation you must find the value of the unknown variable that makes the equation true. You do this by keeping the equation balanced. Whatever you do to one side, you must do to the other side. Start by collecting the variable terms on one side and the constant terms on the other side.

Combining Like Terms
Like terms are terms that have the same variable raised to the same power. For example, three x and five x are like terms. You can add or subtract them to simplify an equation. The terms three x and five are not like terms because one contains x and the other is a constant.

Checking Your Answer
After you solve an equation, always check your answer. Substitute the value you found back into the original equation. If both sides are equal, your answer is correct. If they are not equal, go back and check your working step by step.

Real World Application
Linear equations appear in everyday life. They are used to calculate cost, distance, and speed. If a taxi charges a fixed fee plus a rate per kilometre, the total cost is a linear equation. Understanding how to solve them helps you make accurate decisions."""

BIO_NOTE = """Photosynthesis: An Overview
Photosynthesis is the process by which green plants make their own food using sunlight. The process takes place inside the chloroplasts, which contain a green pigment called chlorophyll. Chlorophyll absorbs light energy from the sun.

The Raw Materials
Photosynthesis needs two main raw materials. The first is carbon dioxide, which plants take in from the air through tiny pores called stomata. The second is water, which plants absorb from the soil through their roots. Sunlight provides the energy needed for the reaction.

The Products
The photosynthesis reaction produces two products. Glucose is the food that the plant uses for energy and growth. Oxygen is released as a waste product into the atmosphere. This means plants are important for producing the oxygen that animals breathe.

The Chemical Equation
The overall equation for photosynthesis can be written as carbon dioxide plus water, in the presence of sunlight and chlorophyll, produces glucose plus oxygen. This simple equation summarises the whole process that happens inside a green plant.

Why Photosynthesis Matters
Photosynthesis is the basis of most food chains. Plants are producers because they create their own food. When animals eat plants, they receive the energy stored in glucose. Without photosynthesis, there would be no oxygen in the atmosphere and no food for animals to eat."""

MATH_PAPER = """Past Exam Paper: Linear Equations
Question One: Solve for x in the equation three x plus four equals thirteen. Show all your working.
Question Two: Simplify the expression four x plus two x minus three.
Question Three: A taxi charges two dollars as a fixed fee plus one dollar per kilometre. Write a linear equation for the cost.
Question Four: Check whether x equals two is a solution of the equation five x minus three equals seven."""

GEO_NOTE = """Map Reading and Contours
A topographic map shows the shape and features of the land using contour lines. A contour line connects points of equal height above sea level. Lines that are close together show a steep slope, while lines far apart show a gentle slope.

Grid References
Grid references are used to locate places on a map. A four figure grid reference locates a square, while a six figure grid reference locates a precise point inside that square. Eastings are read first, then northings.

Settlement Patterns
Settlements can be described by their shape and distribution. A linear settlement follows a road or river. A nucleated settlement is clustered around a central point such as a church or market. A dispersed settlement is spread out with isolated farmsteads."""

GEO_PAPER = """Past Exam Paper: Map Reading
Question One: Define what a contour line represents on a topographic map.
Question Two: Explain how you can tell a steep slope from a gentle slope using contour lines.
Question Three: Distinguish between a linear settlement and a nucleated settlement."""

INDEPENDENT_NOTE = """Introduction to Poetry
Poetry is a form of literature that uses rhythm, sound, and imagery to express emotions and ideas. A poem is often arranged in lines and stanzas rather than in full sentences and paragraphs.
Poetic Devices
Poets use figurative language to create pictures in the reader's mind. A simile compares two things using the words like or as. A metaphor compares two things directly without using like or as. Personification gives human qualities to non-human objects.
Rhyme and Rhythm
Rhyme is the repetition of similar sounds at the end of lines. Rhythm is the pattern of stressed and unstressed syllables in a line. Together they give a poem its musical quality."""


def add_note_ingested(title, subject, category, owner_id, owner_role, class_id, content):
    nid = db.add_note(title, subject, category, owner_id, owner_role, class_id,
                      content, status="active")
    chunks = ai.chunk_content(content)
    db.save_chunks(nid, subject, chunks)
    db.set_note_status(nid, "active", chunk_count=len(chunks))
    return nid


def _seed_interventions(class_id, subject):
    """Create realistic AI-intervention weakness records for a subject."""
    students = db.students_in_class(class_id)
    concepts = {
        "Combining Like Terms": "Many students mix unlike terms. They try to add terms with different variables together.",
        "The Raw Materials": "Students sometimes forget that water comes from the roots and carbon dioxide from the leaves.",
        "Grid References": "Students confuse the order of eastings and northings when reading grid references.",
    }
    # Give the first two students repeated failures on the first concept
    for i, st in enumerate(students[:2]):
        concept = concepts[subject] if subject in concepts else list(concepts.values())[0]
        base = "soccer" if i % 2 == 0 else "music"
        for _ in range(3):
            iv = ai.intervention_log(concept, base)
            db.upsert_weakness(st["id"], subject, concept, add=1,
                               transcript=iv["transcript"], analogy=iv["analogy"],
                               language_note=iv["language_note"])
    # First student also struggles with a second concept (yellow)
    if students:
        iv = ai.intervention_log("Map Reading", "reading")
        db.upsert_weakness(students[0]["id"], subject, "Map Reading", add=1,
                           transcript=iv["transcript"], analogy=iv["analogy"],
                           language_note=iv["language_note"])


def _seed_attempts(class_id, subject):
    """Seed some quiz attempts so the Class Health Score has data (dev/test only)."""
    import random
    notes = db.list_notes(subject=subject, category="notes")
    for st in db.students_in_class(class_id):
        correct_share = 0.9 if st["elo"] > 1200 else (0.4 if st["elo"] < 1150 else 0.7)
        for n in notes:
            for c in db.chunks_for_note(n["id"]):
                for q in db.questions_for_chunk(c["id"]):
                    rng = random.Random(hash((st["id"], q["id"])) % 10**9)
                    for _ in range(3):
                        ok = rng.random() < correct_share
                        db.log_attempt(st["id"], q["id"], subject, c["chunk_index"], 1 if ok else 0)


def seed_if_empty():
    if db.list_users():
        return
    # --- Admin ---
    db.create_user(name="Bongani Tshuma (Admin)", email="admin@bt.co.zw",
                   password_hash=generate_password_hash("admin123"),
                   role="admin", must_change_password=0)

    # --- Classes ---
    form2 = db.create_class("Form 2A")
    db.set_class_subjects(form2, ["Mathematics", "Biology", "English"])
    form3 = db.create_class("Form 3 Geography")
    db.set_class_subjects(form3, ["Geography", "History"])

    # --- Teacher ---
    teacher_id = db.create_user(name="Mrs Chikafu", email="teacher@bt.co.zw",
                                password_hash=generate_password_hash("teacher123"),
                                role="teacher", class_id=form2, must_change_password=0)
    # Teacher teaches two classes/subjects (drives the class dropdown)
    db.set_teacher_classes(teacher_id, [
        (form2, "Mathematics"),
        (form2, "Biology"),
        (form3, "Geography"),
    ])

    # --- School students (Form 2A) ---
    s1 = db.create_user(name="Tatenda Moyo", student_id="BT-001", class_id=form2,
                        password_hash=generate_password_hash("btlearn123"),
                        role="school_student", must_change_password=1,
                        interests="soccer, music", study_start_hour=16, study_end_hour=19,
                        elo=1240, streak=6, points=210)
    db.set_user_subjects(s1, ["Mathematics", "Biology"])
    s2 = db.create_user(name="Ruvarashe Ncube", student_id="BT-002", class_id=form2,
                        password_hash=generate_password_hash("btlearn123"),
                        role="school_student", must_change_password=1,
                        interests="reading, art", study_start_hour=17, study_end_hour=20,
                        elo=1185, streak=3, points=140)
    db.set_user_subjects(s2, ["Mathematics", "Biology"])
    s3 = db.create_user(name="Munyaradzi Dube", student_id="BT-003", class_id=form2,
                        password_hash=generate_password_hash("btlearn123"),
                        role="school_student", must_change_password=1,
                        interests="gaming, tech", study_start_hour=18, study_end_hour=21,
                        elo=1305, streak=9, points=320)
    db.set_user_subjects(s3, ["Mathematics", "Biology"])
    s4 = db.create_user(name="Nyasha Banda", student_id="BT-004", class_id=form2,
                        password_hash=generate_password_hash("btlearn123"),
                        role="school_student", must_change_password=1,
                        interests="farming", study_start_hour=16, study_end_hour=18,
                        elo=1120, streak=1, points=60)
    db.set_user_subjects(s4, ["Mathematics", "Biology"])

    # --- School students (Form 3 Geography) ---
    g1 = db.create_user(name="Tendai Zvoma", student_id="BT-011", class_id=form3,
                        password_hash=generate_password_hash("btlearn123"),
                        role="school_student", must_change_password=1,
                        interests="sports, reading", study_start_hour=17, study_end_hour=20,
                        elo=1215, streak=4, points=175)
    db.set_user_subjects(g1, ["Geography"])
    g2 = db.create_user(name="Kudzai Marufu", student_id="BT-012", class_id=form3,
                        password_hash=generate_password_hash("btlearn123"),
                        role="school_student", must_change_password=1,
                        interests="music", study_start_hour=18, study_end_hour=21,
                        elo=1140, streak=2, points=90)
    db.set_user_subjects(g2, ["Geography"])

    # --- Independent student ---
    ind = db.create_user(name="Chipo (Independent)", email="chipo@gmail.com",
                         password_hash=generate_password_hash("chipo123"),
                         role="independent", must_change_password=0, onboarded=1,
                         academic_level="A-Level", blend_regional=1, learning_mode="video",
                         interests="gaming, tech", study_start_hour=19, study_end_hour=22)
    db.set_user_subjects(ind, ["English", "Mathematics"])

    # --- Curriculum ---
    add_note_ingested("Linear Equations", "Mathematics", "notes", teacher_id, "teacher", form2, MATH_NOTE)
    add_note_ingested("Photosynthesis", "Biology", "notes", teacher_id, "teacher", form2, BIO_NOTE)
    add_note_ingested("Linear Equations Past Paper", "Mathematics", "past_exams", teacher_id, "teacher", form2, MATH_PAPER)
    add_note_ingested("Map Reading and Contours", "Geography", "notes", teacher_id, "teacher", form3, GEO_NOTE)
    add_note_ingested("Map Reading Past Paper", "Geography", "past_exams", teacher_id, "teacher", form3, GEO_PAPER)
    add_note_ingested("Introduction to Poetry", "English", "notes", ind, "independent", None, INDEPENDENT_NOTE)

    # --- Analytics: weaknesses + attempts for a rich teacher dashboard ---
    _seed_interventions(form2, "Mathematics")
    _seed_attempts(form2, "Mathematics")
    _seed_attempts(form2, "Biology")
    _seed_interventions(form3, "Geography")
    _seed_attempts(form3, "Geography")
