"""Structural checks for the generated Grafana dashboard."""
import json
import unittest
from pathlib import Path

DASHBOARD = Path(__file__).parent / 'provisioning/dashboards/public-health-dashboard.json'


class DashboardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dashboard = json.loads(DASHBOARD.read_text())
        cls.panels = {p['title']: p for p in cls.dashboard['panels'] if p['title']}

    def test_requested_cards_and_removals(self):
        for title in ('New patients', 'Patient visits', 'Patient counts',
                      'Provisional encounters', 'Final encounters'):
            self.assertIn(title, self.panels)
        for title in ('Unique patients', 'Recorded encounters', 'Districts',
                      'District ranking', 'Missing district',
                      'Records · period change', 'Latest record in selection'):
            self.assertNotIn(title, self.panels)
        self.assertNotIn('district', [v['name'] for v in self.dashboard['templating']['list']])
        self.assertEqual(len(self.dashboard['panels']), len({p['id'] for p in self.dashboard['panels']}))

    def test_patient_counts_scope(self):
        visit_sql = self.panels['Patient counts']['targets'][0]['rawSql']
        self.assertIn('COUNT(encounter_id)', visit_sql)
        self.assertIn('public.getopdconsultatationDepartmentwiseonly', visit_sql)
        for clause in ("DATE '2026-07-01'", "DATE '2026-09-20'", 'unit_id = 9',
                       "patientname LIKE '%Demo%'", "patientname LIKE '%Palak Singh%'",
                       "patientname LIKE '%Shubham Yede%'"):
            self.assertIn(clause, visit_sql)
        for title, flag in (('Provisional encounters', 'is_provisional'),
                            ('Final encounters', 'is_final')):
            sql = self.panels[title]['targets'][0]['rawSql']
            self.assertIn("COUNT(DISTINCT NULLIF(encounter_number, ''))", sql)
            self.assertIn(f"{flag} = 'Y'", sql)
            self.assertIn('public.diagnosis_dashboard_data', sql)
            self.assertIn('$__timeFilter(created_date)', sql)
            self.assertNotIn('getopdconsultatationDepartmentwiseonly', sql)
        self.assertNotIn('district', DASHBOARD.read_text().lower())

    def test_other_metrics_follow_dashboard_filters(self):
        for title in ('New patients', 'Patient visits', 'Diagnosis records',
                      'Provisional encounters', 'Final encounters'):
            sql = self.panels[title]['targets'][0]['rawSql']
            self.assertIn('$__timeFilter(created_date)', sql)
            for variable in ('unit', 'year', 'month'):
                self.assertIn('${' + variable + '}', sql)


if __name__ == '__main__':
    unittest.main()
