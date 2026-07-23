# מיפוי רעיונות — תהליך BOM Sourcing / Amir Bashan

## Use Case ראשי (MVP)
קבלת BOM והשלמת רכישת רכיבים בפועל, כולל עדכון עגלות קניות אצל ספקים
ודוח סטטוס מפורט.

## טריגר
המהנדס המתכנן מעלה קובץ BOM (Excel) לצ'אט.

## תהליך צעד-אחר-צעד

1. **כניסה לאתרים** — הסוכן נכנס דרך דפדפן לאתרי הספקים הרלוונטיים
   (Digikey, Mouser, LCSC וכו').

2. **עיבוד שורה-שורה** — עבור כל שורה ב-BOM בנפרד:
   - בודק מחיר וזמינות של **הרכיב המקורי**
   - בודק מחיר וזמינות של **כל האלטרנטיבות המאושרות** (עד 4, לפי הנכס הקיים
     שנמצא במפגש 5 — `built-assets.md`)
   - **משווה בין כל האופציות יחד** (מקור + כל האלטרנטיבות) — אין העדפה
     אוטומטית למקור. הזול/הזמין ביותר מנצח, מי שהוא לא יהיה.
   - מכניס את הרכיב שנבחר לעגלת הקניות אצל הספק המתאים

3. **המשכיות** — הסוכן ממשיך אוטומטית לפריט הבא, עד סוף כל ה-BOM
   (לא עוצר לאישור על כל שורה בנפרד).

4. **סיום ודיווח** — בסוף התהליך:
   - כל הרכיבים כבר נמצאים בעגלות הקניות בפועל אצל הספקים
   - הסוכן מוציא **דוח** שהוא בעצם ה-BOM המקורי, ובכל שורה מצוין:
     - היכן (אצל איזה ספק) הפריט הוסף לעגלה
     - מה המחיר
     - אם לא נמצא — מסומן כ**חסר**

## Scope — הוחלט להשאיר מחוץ ל-MVP הראשון
- **מקרה קצה: אין מלאי בשום מקום** (לא במקור, לא באף אלטרנטיבה) —
  לא נכלל בגרסה הראשונה. יטופל בהרחבה עתידית של הכלי.

## עקרונות שכבר הוגדרו (ממפגשים קודמים, רלוונטיים ל-Use Case)
- עלות משלוח — שיקול בין ריכוז אצל ספק אחד לפיצול (ראה `technical-context.md`)
- מדרגות כמות (quantity breaks) — קריטריון החלטה יוגדר במפגש 7
- אימות מול אתרים + טיפול ב-CAPTCHA עם עזרה אנושית (ראה `technical-context.md`)
- זיכרון מצטבר: אישורי המהנדס על אלטרנטיבות נשמרים לשימוש עתידי
  (ראה `built-assets.md`)
## Process fixes from the testing session (Meeting 8)
1. Ask for total production quantity (how many sets) before starting BOM sourcing
2. Ask manual assembly vs. SMT upfront → determines Cut Tape vs. Reel/Digi-Reel, applied
   consistently across all suppliers
3. Compare price/availability across all 3 suppliers (Digi-Key, Mouser, LCSC) — for every
   part, original and all alternatives, not just the top candidates
4. Verify the quantity actually registered in the cart after every add — a click isn't
   proof, check the cart page itself
5. Watch for mismatches between Manufacturer Part Number and Supplier Part Number in the
   BOM (can point to different variants of the same component)
6. CAPTCHA/security-check handling: pause and let it resolve on its own, or ask for human help
