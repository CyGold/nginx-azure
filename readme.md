QueryBeforeIssueQ1 — city lookup13.622msSeq Scan on both tablesQ2 — unsent notifications29.830msSeq Scan + sort on 50k rowsQ3 — triggers per city28.655msSeq Scan on full alert_logs
