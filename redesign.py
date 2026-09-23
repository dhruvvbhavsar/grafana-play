"""Build the provisioned executive dashboard using aggregate SQL only."""
import json
from pathlib import Path

path = Path(__file__).parent / 'provisioning/dashboards/public-health-dashboard.json'
d = json.loads(path.read_text())
ds = {'type': 'postgres', 'uid': 'his-qa-postgres'}
filters = " AND ".join(f"('${{{v}}}' = 'All' OR {col} = '${{{v}}}')" for v, col in [('unit','unit_name'),('year',"to_char(created_date, 'YYYY')"),('month',"to_char(created_date, 'YYYY-MM')")])
where = '$__timeFilter(created_date) AND ' + filters
source = 'public.diagnosis_dashboard_data'
visit_source = 'public.getopdconsultatationDepartmentwiseonly'
visit_where = "CAST(encounter_date AS date) BETWEEN DATE '2026-07-01' AND DATE '2026-09-20' AND unit_id = 9 AND NOT (patientname LIKE '%Demo%' OR patientname LIKE '%Palak Singh%' OR patientname LIKE '%Shubham Yede%')"
panels = []
colors = ['#56D9C9','#73A7FF','#B99AFF','#FFCB70','#F28EAD','#79C99E']

def panel(title, kind, x, y, w, h, sql=None, color=None, description=''):
    p = {'id':len(panels)+1,'title':title,'type':kind,'gridPos':dict(x=x,y=y,w=w,h=h),'description':description}
    if sql:
        p['datasource']=ds
        p['targets']=[dict(refId='A',datasource=ds,rawSql=sql,rawQuery=True,format='time_series' if kind=='timeseries' else 'table')]
        p['fieldConfig']={'defaults':{'unit':'short','decimals':0,'min':0,'color':{'mode':'fixed','fixedColor':color} if color else {'mode':'palette-classic'},'noValue':'No records'},'overrides':[]}
    if kind=='stat':
        p['options']={'colorMode':'value','graphMode':'none','justifyMode':'center','textMode':'value','reduceOptions':{'calcs':['lastNotNull'],'fields':'','values':False},'text':{'valueSize':36}}
    elif kind=='barchart':
        p['options']={'orientation':'horizontal','barRadius':0.15,'barWidth':0.65,'groupWidth':0.75,'showValue':'always','stacking':'none','legend':{'showLegend':False},'tooltip':{'mode':'multi','sort':'desc'}}
    elif kind=='timeseries':
        p['fieldConfig']['defaults']['custom']={'drawStyle':'line','lineWidth':2,'fillOpacity':12,'gradientMode':'opacity','showPoints':'always','pointSize':5,'spanNulls':False,'axisLabel':'Count'}
        p['options']={'legend':{'showLegend':True,'displayMode':'table','placement':'bottom','calcs':['sum']},'tooltip':{'mode':'multi','sort':'desc'}}
    elif kind=='piechart':
        p['options']={'pieType':'donut','displayLabels':['percent'],'legend':{'showLegend':True,'placement':'right','displayMode':'table','values':['value']},'reduceOptions':{'values':True,'calcs':['lastNotNull'],'fields':''},'tooltip':{'mode':'single'}}
    panels.append(p)
    return p

def text(title, content, y, h=2):
    p=panel(title,'text',0,y,24,h)
    p['transparent']=True
    p['options']={'mode':'markdown','content':content}

text('', '# Public health · Executive overview\nDiagnosis activity and patient composition in one place. **Use the filters above to explore.** Patient counts alone uses a fixed date range and unit.',0,3)
metrics=[('Diagnosis records','COUNT(*)'),('New patients',"COUNT(DISTINCT NULLIF(uhid_number, ''))"),('Patient visits',"COUNT(DISTINCT NULLIF(encounter_number, ''))"),('Patient counts',None),('Health units',"COUNT(DISTINCT NULLIF(unit_name, ''))"),('Diagnosis types',"COUNT(DISTINCT NULLIF(diagnosis_desc, ''))")]
for i,(title,expr) in enumerate(metrics):
    if title == 'Patient counts':
        sql=f'SELECT COUNT(encounter_id) AS value FROM {visit_source} WHERE {visit_where}'
        description='Patient visits from the OPD consultation view, 1 Jul–20 Sep 2026, unit 9, excluding the specified test names. Not controlled by dashboard filters.'
    else:
        sql=f'SELECT {expr} AS value FROM {source} WHERE {where}'
        description='Within the selected period and filters. New patients are distinct UHIDs; patient visits are distinct recorded encounter numbers in the diagnosis data.'
    panel(title,'stat',i*4,3,4,4,sql,colors[i],description)
text('', '### Activity & encounter status\nDaily diagnosis volumes and encounter status follow dashboard filters.',7)
sql=f"WITH days AS (SELECT generate_series(date_trunc('day', $__timeFrom()::timestamp), date_trunc('day', $__timeTo()::timestamp), interval '1 day') AS time), counts AS (SELECT date_trunc('day',created_date) AS time, COUNT(*)::float AS records, COUNT(DISTINCT uhid_number)::float AS patients FROM {source} WHERE {where} GROUP BY 1) SELECT days.time, COALESCE(records,0) AS \"Diagnosis records\", COALESCE(patients,0) AS \"Daily new patients (distinct UHIDs)\" FROM days LEFT JOIN counts USING(time) ORDER BY 1"
panel('Daily activity','timeseries',0,9,16,8,sql,description='Zero-filled days. Daily distinct UHIDs must not be summed to obtain period distinct UHIDs.')
for i,(title,flag) in enumerate([('Provisional encounters','is_provisional'),('Final encounters','is_final')]):
    status_sql=f"SELECT COUNT(DISTINCT NULLIF(encounter_number, '')) FILTER (WHERE {flag} = 'Y') AS value FROM {source} WHERE {where}"
    panel(title,'stat',16,9+i*4,8,4,status_sql,colors[1+i], 'Distinct encounter numbers flagged as this diagnosis status within the selected dashboard period and filters.')
text('', '### Where activity is concentrated\nTop diagnoses reflect recorded diagnosis volume, not population-adjusted disease rates.',17)
panel('Top diagnoses','barchart',0,19,24,9,f"SELECT COALESCE(NULLIF(diagnosis_desc,''),'Unknown') AS label, COUNT(*)::bigint AS \"Records\" FROM {source} WHERE {where} GROUP BY 1 ORDER BY 2 DESC,1 LIMIT 10",colors[1])
text('', '### Patient & service composition\nDemographics show diagnosis-record distribution; a patient can contribute multiple records.',28)
panel('Gender · record distribution','piechart',0,30,8,8,f"SELECT COALESCE(NULLIF(gender_name,''),'Unknown') AS label, COUNT(*) AS value FROM {source} WHERE {where} GROUP BY 1 ORDER BY 2 DESC")
age="CASE WHEN btrim(ageyear) ~ '^[0-9]+([.][0-9]+)?$' THEN CASE WHEN btrim(ageyear)::numeric < 18 THEN '0–17' WHEN btrim(ageyear)::numeric < 35 THEN '18–34' WHEN btrim(ageyear)::numeric < 60 THEN '35–59' WHEN btrim(ageyear)::numeric <= 120 THEN '60+' ELSE 'Unknown' END ELSE 'Unknown' END"
panel('Age · record distribution','barchart',8,30,8,8,f'SELECT {age} AS label,COUNT(*) AS value FROM {source} WHERE {where} GROUP BY 1 ORDER BY 1',colors[2],'Numeric ageyear values only; invalid or implausible values appear as Unknown.')
panel('Specialty · records','barchart',16,30,8,8,f"SELECT COALESCE(NULLIF(speciality_name,''),'Unknown') AS label,COUNT(*) AS value FROM {source} WHERE {where} GROUP BY 1 ORDER BY 2 DESC LIMIT 8",colors[3])
text('', '### Disease surveillance\nCategory flags can overlap. Counts across categories should not be added together.',38)
flags=[('Communicable','is_communicable'),('Non-communicable','is_non_communicable'),('Notifiable','is_notifiable'),('Vector-borne','is_vector_borne'),('Occupational','is_occupational_notifiable')]
cat=' UNION ALL '.join(f"SELECT '{label}' AS label,COUNT(*) FILTER (WHERE {flag}='Y') AS value FROM selected" for label,flag in flags)
panel('Disease category counts','barchart',0,40,10,9,f'WITH selected AS (SELECT * FROM {source} WHERE {where}) {cat}',colors[4])
series=', '.join(f'COUNT(*) FILTER (WHERE {flag}=\'Y\')::float AS "{label}"' for label,flag in flags)
panel('Category trends','timeseries',10,40,14,9,f"SELECT date_trunc('day',created_date) AS time,{series} FROM {source} WHERE {where} GROUP BY 1 ORDER BY 1")
text('', '### Coverage notes\nMissing fields can affect rankings and demographic interpretation. Auto-refresh: **5 minutes**.',49)
for i,(title,col) in enumerate([('Missing gender','gender_name'),('Missing diagnosis','diagnosis_desc')]):
    panel(title,'stat',i*12,51,12,3,f"SELECT COUNT(*) FILTER (WHERE NULLIF(btrim({col}),'') IS NULL) AS value FROM {source} WHERE {where}",colors[3])
d['panels']=panels
d['templating']['list']=[v for v in d['templating']['list'] if v['name'] != 'district']
d['version']=d.get('version',1)+1
d['description']='Public-health executive overview with activity, coverage, demographics and disease surveillance. Aggregate data only.'
path.write_text(json.dumps(d,indent=2)+'\n')
