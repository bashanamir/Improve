"""
בלוק 5 — כתיבה לקובץ (append)
קלט: MD מעובד (תובנות משיעור)
פלט: master-library/master-course-lessons.md — מעודכן

חשוב: מוסיפים (append) — לא דורסים תוכן קודם. כל ריצה מוסיפה סעיף חדש.
"""
import os
from datetime import datetime

KNOWLEDGE_FILE = "master-library/master-course-lessons.md"


def append_insights(insights_md, lesson_number):
    """נקודת הכניסה של הבלוק — מוסיף את התובנות למסמך הידע."""
    os.makedirs(os.path.dirname(KNOWLEDGE_FILE), exist_ok=True)
    is_new = not os.path.exists(KNOWLEDGE_FILE)

    with open(KNOWLEDGE_FILE, "a", encoding="utf-8") as f:
        if is_new:
            f.write("# מסמך ידע — קורס טירונות סוכנים\n\n")
            f.write("> מסמך זה מוזן אוטומטית לאחר כל שיעור. הסוכן האישי (BOM Manager) קורא ממנו.\n\n")
        f.write(f"\n---\n")
        f.write(f"<!-- עודכן: {datetime.now().strftime('%Y-%m-%d %H:%M')} -->\n\n")
        f.write(insights_md.strip())
        f.write("\n")

    print(f"מסמך הידע עודכן: {KNOWLEDGE_FILE} (שיעור {lesson_number} נוסף)")
    return KNOWLEDGE_FILE


if __name__ == "__main__":
    append_insights("## שיעור בדיקה\n\n### מה נלמד\n- בדיקה שהקוד עובד", lesson_number=0)
