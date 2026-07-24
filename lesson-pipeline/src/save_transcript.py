"""
בלוק 3ב — שמירת התמלול הגולמי
קלט: תמלול גולמי מלא (טקסט)
פלט: master-library/transcripts/lesson-NN.md

חשוב: נשמר תמיד, גם אם שלב העיבוד (בלוק 4) נכשל אחר כך.
מספור: לפי סדר הרצה (1, 2, 3...) — לא לפי שם הקובץ בדרייב.
"""
import os

COUNTER_PATH = "knowledge/lesson_counter.txt"
TRANSCRIPTS_DIR = "master-library/transcripts"


def get_next_lesson_number():
    """קורא את המספר האחרון ומחזיר את הבא בתור. מתחיל מ-1 אם אין קובץ."""
    if not os.path.exists(COUNTER_PATH):
        os.makedirs(os.path.dirname(COUNTER_PATH), exist_ok=True)
        return 1
    with open(COUNTER_PATH, "r") as f:
        last = int(f.read().strip() or 0)
    return last + 1


def save_counter(n):
    os.makedirs(os.path.dirname(COUNTER_PATH), exist_ok=True)
    with open(COUNTER_PATH, "w") as f:
        f.write(str(n))


def save_raw_transcript(transcript_text, lesson_number=None):
    """נקודת הכניסה של הבלוק — שומר את התמלול הגולמי בנתיב הקבוע."""
    if lesson_number is None:
        lesson_number = get_next_lesson_number()

    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
    file_name = f"lesson-{lesson_number:02d}.md"
    path = os.path.join(TRANSCRIPTS_DIR, file_name)

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# שיעור {lesson_number} — תמלול גולמי\n\n")
        f.write(transcript_text)

    save_counter(lesson_number)
    print(f"תמלול גולמי נשמר: {path}")
    return path, lesson_number


if __name__ == "__main__":
    save_raw_transcript("בדיקה — טקסט לדוגמה.")
