# 층별 진행 현황

간략 엔진, 3600 s, 기존 후보 점수 1위. 최악 급기 탐색 결과가 아닌 대표 시나리오. 미실행/실패는 —. 최고값은 평가된 표본 범위만 사용하며, 일부 미평가 시각과 셀은 JSON의 partial_conditions에 기록.

|건물|층|화점|상태|적분 s|전체 s|연소 실 수|FO 최고|FGI 최고|BD 최고|
|---|---|---|---|---:|---:|---:|---|---|---|
|ganghwa|3F|CAD_3F_R1|complete|37.12|46.64|1|39.7 @ 3600s (CAD_3F_R1)|0.0 @ 10s (CAD_3F_R1)|0.0 @ 10s (CAD_3F_R1)|
|parkmarine|5F|CAD_5F_R16|complete|51.42|58.06|1|134.3 @ 470s (CAD_5F_R16)|78.1 @ 690s (CAD_5F_R16)|74.9 @ 700s (CAD_5F_R16)|
|ganghwa|1F|CAD_1F_R9|complete|974.71|983.70|4|104.3 @ 1870s (CAD_1F_R0)|114.7 @ 1020s (CAD_1F_R31)|176.8 @ 2300s (CAD_1F_R17)|
|ganghwa|2F|CAD_2F_R7|complete|328.44|337.00|1|108.8 @ 910s (CAD_2F_R7)|78.3 @ 1570s (CAD_2F_R7)|79.4 @ 1410s (CAD_2F_R7)|
|ganghwa|4F|CAD_4F_R0|complete|68.31|78.51|1|52.2 @ 1770s (CAD_4F_R0)|46.3 @ 1970s (CAD_4F_R0)|41.6 @ 2040s (CAD_4F_R0)|
|ganghwa|5F|CAD_5F_R12|complete|24.21|32.69|1|118.6 @ 2510s (CAD_5F_R12)|69.4 @ 2940s (CAD_5F_R12)|56.1 @ 2950s (CAD_5F_R12)|
|ganghwa|6F|CAD_6F_R2|complete|121.40|133.42|1|87.8 @ 1840s (CAD_6F_R2)|59.0 @ 1980s (CAD_6F_R2)|59.0 @ 1980s (CAD_6F_R2)|
|ganghwa|7F|CAD_7F_R0|complete|46.93|55.75|1|58.4 @ 1140s (CAD_7F_R0)|58.9 @ 1290s (CAD_7F_R0)|55.3 @ 1330s (CAD_7F_R0)|
|ganghwa|B1|—|blocked|—|—|—|—|—|—|
|ganghwa|PH|—|blocked|—|—|—|—|—|—|
|parkmarine|10F|CAD_10F_R15|failed|—|299.41|—|—|—|—|
|parkmarine|1F|CAD_1F_R3|complete|8.91|14.06|1|49.7 @ 180s (CAD_1F_R3)|0.0 @ 10s (CAD_1F_R5)|0.0 @ 10s (CAD_1F_R5)|
|parkmarine|2F|CAD_2F_R1|complete|23.28|27.55|1|96.1 @ 880s (CAD_2F_R1)|101.1 @ 1190s (CAD_2F_R3)|69.2 @ 1210s (CAD_2F_R1)|
|parkmarine|3F|CAD_3F_R1|complete|20.10|24.36|1|87.0 @ 1570s (CAD_3F_R1)|80.6 @ 1640s (CAD_3F_R3)|59.1 @ 1690s (CAD_3F_R1)|
|parkmarine|4F|CAD_4F_R11|complete|42.36|47.72|1|133.9 @ 480s (CAD_4F_R11)|75.1 @ 690s (CAD_4F_R11)|73.3 @ 740s (CAD_4F_R11)|
|parkmarine|6F|CAD_6F_R16|complete|42.09|47.66|1|133.9 @ 480s (CAD_6F_R16)|77.3 @ 690s (CAD_6F_R16)|74.1 @ 690s (CAD_6F_R16)|
|parkmarine|7F|CAD_7F_R16|complete|41.57|47.06|1|133.9 @ 480s (CAD_7F_R16)|77.1 @ 690s (CAD_7F_R16)|74.2 @ 690s (CAD_7F_R16)|
|parkmarine|8F|CAD_8F_R11|complete|42.51|48.03|1|133.6 @ 480s (CAD_8F_R11)|73.9 @ 710s (CAD_8F_R11)|73.9 @ 710s (CAD_8F_R11)|
|parkmarine|9F|CAD_9F_R15|complete|41.76|46.92|1|134.0 @ 480s (CAD_9F_R15)|79.0 @ 700s (CAD_9F_R15)|76.9 @ 710s (CAD_9F_R15)|
|parkmarine|B1|—|blocked|—|—|—|—|—|—|
|parkmarine|B2|CAD_B2_R5|complete|44.15|49.95|2|100.2 @ 850s (CAD_B2_R5)|73.1 @ 1040s (CAD_B2_R5)|85.2 @ 1010s (CAD_B2_R5)|
|parkmarine|B3|CAD_B3_R6|complete|68.42|72.95|1|17.4 @ 3150s (CAD_B3_R6)|7.4 @ 3600s (CAD_B3_R6)|5.5 @ 3600s (CAD_B3_R6)|
|parkmarine|PH|CAD_PH_R4|complete|1.87|5.06|1|87.2 @ 2920s (CAD_PH_R4)|0.0 @ 10s (CAD_PH_R0)|0.0 @ 10s (CAD_PH_R0)|
|showroom|1F|CAD_1F_R6|complete|164.97|170.88|3|55.0 @ 760s (CAD_1F_R6)|68.2 @ 940s (CAD_1F_R6)|62.7 @ 960s (CAD_1F_R6)|
|showroom|2F|CAD_2F_R27|complete|14.04|20.16|1|56.6 @ 850s (CAD_2F_R27)|51.7 @ 1080s (CAD_2F_R27)|43.5 @ 1130s (CAD_2F_R27)|
