Excel-content-saved-as-.csv tolerance demo
=========================================

These two files prove the reader accepts real-world Excel CSV exports:

  qa_review_excel_bom_semicolon.csv  UTF-8 BOM + ';' delimiter + aliased headers
      timestamp -> ts | approved_by -> reviewer_id | employee_id -> agent_id
  ai_audit_excel_utf16_tab.csv      UTF-16 LE + TAB delimiter + date_time -> ts

Supported: UTF-8 / UTF-8-BOM / UTF-16 / CP1252 / Latin-1 encodings and
comma / semicolon / tab / pipe delimiters (auto-detected). Column aliases
are resolved automatically. Files are strictly read-only and never rewritten.

To verify: python3.11 evidence.py --out <folder containing a copy> --validate-only
