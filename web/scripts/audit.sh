#!/bin/sh
# Design audit of the broadcast player and the guided tour at 1920×1080, 1440×900 and 390×844:
# moment replays with each kind of telestration, the evidence panel, the insights feed and the
# timeline. Needs the API on :8000 and Vite on :5173. Exits 1 if any audit finds a problem.
BASE=${BASE:-http://localhost:5173}
URLS="
/broadcast?run=r_m_1000_1ad2f33e&from=2031000&auditAt=3000
/broadcast?run=r_m_1000_1ad2f33e&from=2049000&auditAt=9000
/broadcast?run=r_m_1000_1ad2f33e&from=5407500&auditAt=9000
/broadcast?run=r_m_1000_1ad2f33e&from=1749000&auditAt=9000
/broadcast?run=r_m_1003_ac9d4e3d&from=3245500&auditAt=9000
/broadcast?run=r_m_1009_99a9845c&from=5405500&auditAt=9000
/tour?step=4&auditAt=27000
"
status=0
for size in "1920 1080" "1440 900" "390 844"; do
  for u in $URLS; do
    node "$(dirname "$0")/capture.mjs" audit "$BASE$u" $size || status=1
  done
done
exit $status
