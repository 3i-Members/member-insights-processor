WITH ids AS (
  SELECT contact_id FROM UNNEST([
    'CNT-Zyj007490','CNT-JP7006505','CNT-yRN002304','CNT-Xzl008528','CNT-iR6006466',
    'CNT-BgR002536','CNT-lh5007158','CNT-qt3007001','CNT-ac8006860','CNT-TTg007821',
    'CNT-Z20002884','CNT-EMV007679','CNT-yUD009255','CNT-hn4009264','CNT-WIf006460',
    'CNT-qZI007260','CNT-9kY009074','CNT-Rsn002192','CNT-QeY002842','CNT-Bde002479',
    'CNT-OmT008649','CNT-CTl002281','CNT-q6y007390','CNT-gu1002782','CNT-miS002255',
    'CNT-lDt008799','CNT-8iy006524','CNT-FYs006457','CNT-p4B006912','CNT-0Ey002784',
    'CNT-k3P002883','CNT-7Nn007403','CNT-WQC009289','CNT-6Hj002216','CNT-ff7009114',
    'CNT-zBO002427','CNT-xXw002522','CNT-ncW002227','CNT-JvQ006805','CNT-z8M008158',
    'CNT-QxQ006164','CNT-Glb008800','CNT-vQ7009292','CNT-moH002469','CNT-VlI007523',
    'CNT-pZg002306','CNT-zwk006174','CNT-LCf002387','CNT-Moi002590','CNT-w7d007639',
    'CNT-zZa002518','CNT-TgK006719','CNT-nxl006336','CNT-Muv006147','CNT-DQ9008836',
    'CNT-pkQ006541','CNT-gB5006684','CNT-7Kq008489','CNT-ehn007946','CNT-2uB006657',
    'CNT-NJn006501','CNT-6hY008998','CNT-zd6007893','CNT-WjY002426','CNT-lwX002544',
    'CNT-Xdc008002','CNT-UUX008530','CNT-ihP008007','CNT-uth002565','CNT-qSu002540',
    'CNT-cPQ009145','CNT-KLu002534','CNT-atZ008584','CNT-hdw008747','CNT-tPW009280',
    'CNT-srH002651','CNT-3HG002874','CNT-rEr007422','CNT-g6J002405','CNT-MjF007457',
    'CNT-Dp4006913','CNT-raU006210','CNT-SY6007378','CNT-z02006937','CNT-jzp007587',
    'CNT-7s5008501','CNT-ARU009225','CNT-xEW008325','CNT-QP5008851','CNT-qYV006932',
    'CNT-tlN008009','CNT-rcM002909','CNT-aHg002542','CNT-0o9009111'
  ]) AS contact_id
),
last_proc AS (
  SELECT contact_id, MAX(processed_at) AS last_processed
  FROM `i-sales-analytics.elvis.eni_processing_log`
  WHERE processing_status = 'completed'
    AND processor_system_prompt_key = {{system_prompt}}
    AND processor_generator = {{generator}}
  GROUP BY contact_id
),
available AS (
  SELECT DISTINCT eva.contact_id, lp.last_processed
  FROM `i-sales-analytics.3i_analytics.eni_vectorizer__all` eva
  JOIN ids USING (contact_id)
  LEFT JOIN last_proc lp USING (contact_id)
  WHERE eva.description IS NOT NULL AND TRIM(eva.description) != ''
)
SELECT contact_id
FROM available
WHERE last_processed IS NULL
ORDER BY contact_id
 limit 1000000
 offset 0


