# Copyright 2020 (c) Cognizant Digital Business, Evolutionary AI. All rights reserved. Issued under the Apache 2.0 License.

import os
from datetime import datetime, timedelta
import unittest

import numpy as np
import pandas as pd

from covid_xprize.validation.scenario_generator import get_raw_data, generate_scenario

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
FIXTURES_PATH = os.path.join(ROOT_DIR, 'fixtures')
DATA_FILE = os.path.join(FIXTURES_PATH, "OxCGRT_latest.csv")
# This file contains data for Belgium and Brazil, where Brazil has 1 more day of data than Belgium
DATES_MISMATCH_DATA_FILE = os.path.join(FIXTURES_PATH, "OxCGRT_dates_mismatch.csv")

MAX_NPIS_DICT = {
    "C1_School closing": 3,
    "C2_Workplace closing": 3,
    "C3_Cancel public events": 2,
    "C4_Restrictions on gatherings": 4,
    "C5_Close public transport": 2,
    "C6_Stay at home requirements": 3,
    "C7_Restrictions on internal movement": 2,
    "C8_International travel controls": 4,
    "E1_Income support": 2,
    "E2_Debt/contract relief": 2,
    "E3_Fiscal measures": 1957600000000.00000,  # Max from file
    "E4_International support": 834353051822.00000,  # Max from file
    "H1_Public information campaigns": 2,
    "H2_Testing policy": 3,
    "H3_Contact tracing": 2,
    "H4_Emergency investment in healthcare": 242400000000.00000,  # Max from file
    "H5_Investment in vaccines": 100404615615.00000,  # Max from file
    "H6_Facial Coverings": 4,
    "H7_Vaccination policy": 5,
    "H8_Protection of elderly people": 3,
    # "M1_Wildcard": "text",  # Contains text
    "V1_Vaccine Prioritisation (summary)": 2,
    "V2A_Vaccine Availability (summary)": 3,
    # "V2B_Vaccine age eligibility/availability age floor (general population summary)": "0-4 yrs",  # Lowest age group
    # "V2C_Vaccine age eligibility/availability age floor (at risk summary)": "0-4 yrs",  # Lowest age group
    "V2D_Medically/ clinically vulnerable (Non-elderly)": 3,
    "V2E_Education": 2,
    "V2F_Frontline workers  (non healthcare)": 2,
    "V2G_Frontline workers  (healthcare)": 2,
    "V3_Vaccine Financial Support (summary)": 5,
    "V4_Mandatory Vaccination (summary)": 1
}

NPI_COLUMNS = list(MAX_NPIS_DICT.keys())
MIN_NPIS = [0] * len(NPI_COLUMNS)
MAX_NPIS = list(MAX_NPIS_DICT.values())
# Sets each NPI to level 1
ONE_NPIS = [1] * len(NPI_COLUMNS)

DATE_FORMAT = "%Y-%m-%d"
INCEPTION_DATE = "2020-01-01"


class TestScenarioGenerator(unittest.TestCase):
    """
    Tests generating different NPI scenarios.

    Definitions:
    I = inception date = 2020-01-01 (earliest available data)
    LK = last known date (for each country) in the latest available data
    S = start date of the scenario
    E = end date of the scenario

    Time wise, the following kind of scenarios can be applied:
    1. Counterfactuals: I____S_____E____LK where E can equal LK
    2. Future:          I____S_____LK___E where S can equal LK
    3. Mind the gap:    I____LK    S____E

    For each case, we check each type of scenario: freeze, MIN, MAX, custom

    Scenarios can be applied to: 1 country, several countries, all countries
    """

    @classmethod
    def setUpClass(cls):
        # Load the csv data only once
        cls.latest_df = get_raw_data(DATA_FILE, latest=True, npi_columns=NPI_COLUMNS)

    def test_generate_scenario_counterfactual_freeze(self):
        # Simulate Italy did not start increasing NPIs on Feb 22, but instead waited before changing them
        before_day = pd.to_datetime("2020-02-21", format=DATE_FORMAT)
        frozen_npis_df = self.latest_df[(self.latest_df.CountryName == "Italy") &
                                        (self.latest_df.Date == before_day)][NPI_COLUMNS].reset_index(drop=True)
        frozen_npis = list(frozen_npis_df.values[0])
        self._check_counterfactual("Freeze", frozen_npis)

    def test_generate_scenario_counterfactual_min(self):
        # Simulate Italy lifted all NPIs for a period
        self._check_counterfactual("MIN", MIN_NPIS)

    def test_generate_scenario_counterfactual_max(self):
        # Simulate Italy maxed out all NPIs for a period
        self._check_counterfactual("MAX", MAX_NPIS)

    def test_generate_scenario_counterfactual_custom(self):
        # Simulate Italy used custom NPIs for a period: each NPI set to 1 for 34 consecutive days
        scenario = [ONE_NPIS] * 34
        self._check_counterfactual(scenario, scenario[0])

    def _check_counterfactual(self, scenario, scenario_npis):
        # Simulate Italy applied the passed NPIs for this period
        start_date_str = "2020-02-22"
        end_date_str = "2020-03-26"
        countries = ["Italy"]
        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario=scenario,
                                        max_npis_dict=MAX_NPIS_DICT)
        self.assertIsNotNone(scenario_df)
        # Misleading name but checks the elements, regardless of order
        self.assertCountEqual(countries, scenario_df.CountryName.unique(), "Not the requested countries")
        self.assertFalse(scenario_df["Date"].duplicated().any(), "Expected 1 row per date only")
        start_date = pd.to_datetime(start_date_str, format=DATE_FORMAT)
        end_date = pd.to_datetime(end_date_str, format=DATE_FORMAT)
        before_day = start_date - np.timedelta64(1, 'D')
        before_day_npis = scenario_df[scenario_df.Date == before_day][NPI_COLUMNS].reset_index(drop=True)
        before_day_npis_truth = self.latest_df[(self.latest_df.CountryName == "Italy") &
                                               (self.latest_df.Date == before_day)][NPI_COLUMNS].reset_index(drop=True)
        # Check the day before the scenario is correct
        pd.testing.assert_frame_equal(before_day_npis_truth, before_day_npis, "Not the expected frozen NPIs")
        # For the right period (+1 to include start and end date)
        nb_days = (end_date - start_date).days + 1
        for i in range(nb_days):
            check_day = start_date + np.timedelta64(i, 'D')
            check_day_npis_df = scenario_df[scenario_df.Date == check_day][NPI_COLUMNS].reset_index(drop=True)
            check_day_npis = list(check_day_npis_df.values[0])
            self.assertListEqual(scenario_npis, check_day_npis)
        # Check Mar 27 is different from frozen day
        after_day = end_date + np.timedelta64(1, 'D')
        after_day_npis_df = scenario_df[scenario_df.Date == after_day][NPI_COLUMNS].reset_index(drop=True)
        self.assertTrue((scenario_npis - after_day_npis_df.values[0]).any(),
                        "Expected NPIs to be different")
        # Check 27 is indeed equal to truth
        after_day_npis_truth = self.latest_df[(self.latest_df.CountryName == "Italy") &
                                              (self.latest_df.Date == after_day)
                                              ][NPI_COLUMNS].reset_index(drop=True)
        pd.testing.assert_frame_equal(after_day_npis_truth, after_day_npis_df, "Not the expected unfrozen NPIs")

    def test_generate_scenario_future_freeze(self):
        # Simulate Italy froze it's NPIS for 1 week after last known date
        countries = ["Italy"]
        start_date_str = "2020-07-01"
        # Set end date to 1 week from last known date
        last_known_date = self.latest_df[self.latest_df.CountryName == "Italy"].Date.max()
        end_date_str = (last_known_date + pd.DateOffset(7)).strftime(DATE_FORMAT)
        scenario = "Freeze"

        before_day = pd.to_datetime("2020-06-30", format=DATE_FORMAT)
        frozen_npis_df = self.latest_df[(self.latest_df.CountryName == "Italy") &
                                        (self.latest_df.Date == before_day)][NPI_COLUMNS].reset_index(drop=True)
        scenario_npis = list(frozen_npis_df.values[0])

        # Generate the scenario
        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario=scenario,
                                        max_npis_dict=MAX_NPIS_DICT)

        # Check it
        self._check_future(start_date_str=start_date_str,
                           end_date_str=end_date_str,
                           scenario_df=scenario_df[scenario_df.CountryName == countries[0]],
                           scenario_npis=scenario_npis,
                           country=countries[0])

    def test_generate_scenario_future_min(self):
        # Simulate Italy lifted all NPIs for 1 week after last known date
        countries = ["Italy"]
        start_date_str = "2020-07-01"
        # Set end date to 1 week from last known date
        last_known_date = self.latest_df[self.latest_df.CountryName == "Italy"].Date.max()
        end_date_str = (last_known_date + pd.DateOffset(7)).strftime(DATE_FORMAT)
        scenario = "MIN"
        scenario_npis = MIN_NPIS

        # Generate the scenario
        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario=scenario,
                                        max_npis_dict=MAX_NPIS_DICT)

        # Check it
        self._check_future(start_date_str=start_date_str,
                           end_date_str=end_date_str,
                           scenario_df=scenario_df[scenario_df.CountryName == countries[0]],
                           scenario_npis=scenario_npis,
                           country=countries[0])

    def test_generate_scenario_future_max(self):
        # Simulate Italy maxed out all NPIs for 1 week after last known date
        countries = ["Italy"]
        start_date_str = "2020-07-01"
        # Set end date to 1 week from last known date
        last_known_date = self.latest_df[self.latest_df.CountryName == "Italy"].Date.max()
        end_date_str = (last_known_date + pd.DateOffset(7)).strftime(DATE_FORMAT)
        scenario = "MAX"
        scenario_npis = MAX_NPIS

        # Generate the scenario
        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario=scenario,
                                        max_npis_dict=MAX_NPIS_DICT)

        # Check it
        self._check_future(start_date_str=start_date_str,
                           end_date_str=end_date_str,
                           scenario_df=scenario_df[scenario_df.CountryName == countries[0]],
                           scenario_npis=scenario_npis,
                           country=countries[0])

    def test_generate_scenario_future_custom(self):
        # Simulate Italy used custom NPIs for 1 week after last known date
        countries = ["Italy"]
        start_date_str = "2020-07-01"
        # Set end date to 1 week from last known date
        last_known_date = self.latest_df[self.latest_df.CountryName == "Italy"].Date.max()
        end_date_str = (last_known_date + pd.DateOffset(7)).strftime(DATE_FORMAT)
        start_date = pd.to_datetime(start_date_str, format=DATE_FORMAT)
        end_date = pd.to_datetime(end_date_str, format=DATE_FORMAT)
        nb_days = (end_date - start_date).days + 1  # +1 to include start date
        scenario = [ONE_NPIS] * nb_days

        # Generate the scenario
        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario=scenario,
                                        max_npis_dict=MAX_NPIS_DICT)
        # Check it
        self._check_future(start_date_str=start_date_str,
                           end_date_str=end_date_str,
                           scenario_df=scenario_df[scenario_df.CountryName == countries[0]],
                           scenario_npis=scenario[0],
                           country=countries[0])

    def test_generate_scenario_future_from_last_known_date_freeze(self):
        # Simulate Italy freezes NPIS for 1 week after last known date
        countries = ["Italy"]
        start_date_str = None
        scenario = "Freeze"
        # Set end date to 1 week from last known date
        last_known_date = self.latest_df[self.latest_df.CountryName == "Italy"].Date.max()
        end_date_str = (last_known_date + pd.DateOffset(7)).strftime(DATE_FORMAT)
        frozen_npis_df = self.latest_df[(self.latest_df.CountryName == "Italy") &
                                        (self.latest_df.Date == last_known_date)][NPI_COLUMNS].reset_index(drop=True)
        scenario_npis = list(frozen_npis_df.values[0])

        # Generate the scenario
        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario=scenario,
                                        max_npis_dict=MAX_NPIS_DICT)

        # Check it
        self._check_future(start_date_str=start_date_str,
                           end_date_str=end_date_str,
                           scenario_df=scenario_df[scenario_df.CountryName == countries[0]],
                           scenario_npis=scenario_npis,
                           country=countries[0])

    def test_generate_scenario_future_from_last_known_date_min(self):
        # Simulate Italy lifts all NPIs for 1 week after last known date
        countries = ["Italy"]
        start_date_str = None
        # Set end date to 1 week from last known date
        last_known_date = self.latest_df[self.latest_df.CountryName == "Italy"].Date.max()
        end_date_str = (last_known_date + pd.DateOffset(7)).strftime(DATE_FORMAT)

        scenario = "MIN"
        scenario_npis = MIN_NPIS

        # Generate the scenario
        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario=scenario,
                                        max_npis_dict=MAX_NPIS_DICT)

        # Check it
        self._check_future(start_date_str=start_date_str,
                           end_date_str=end_date_str,
                           scenario_df=scenario_df[scenario_df.CountryName == countries[0]],
                           scenario_npis=scenario_npis,
                           country=countries[0])

    def test_generate_scenario_future_from_last_known_date_max(self):
        # Simulate Italy maxes out NPIs for 1 week after last known date
        countries = ["Italy"]
        start_date_str = None
        # Set end date to 1 week from last known date
        last_known_date = self.latest_df[self.latest_df.CountryName == "Italy"].Date.max()
        end_date_str = (last_known_date + pd.DateOffset(7)).strftime(DATE_FORMAT)

        scenario = "MAX"
        scenario_npis = MAX_NPIS

        # Generate the scenario
        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario=scenario,
                                        max_npis_dict=MAX_NPIS_DICT)

        # Check it
        self._check_future(start_date_str=start_date_str,
                           end_date_str=end_date_str,
                           scenario_df=scenario_df[scenario_df.CountryName == countries[0]],
                           scenario_npis=scenario_npis,
                           country=countries[0])

    def test_generate_scenario_future_from_last_known_date_custom(self):
        # Simulate Italy uses custom NPIs for 1 week after last known date
        countries = ["Italy"]
        last_known_date = self.latest_df[self.latest_df.CountryName == "Italy"].Date.max()
        start_date = last_known_date + np.timedelta64(1, 'D')
        # Set end date to 1 week from last known date
        end_date_str = (last_known_date + pd.DateOffset(7)).strftime(DATE_FORMAT)
        end_date = pd.to_datetime(end_date_str, format=DATE_FORMAT)
        nb_days = (end_date - start_date).days + 1  # +1 to include start date
        scenario = [ONE_NPIS] * nb_days

        # Generate the scenario
        scenario_df = generate_scenario(None,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario=scenario,
                                        max_npis_dict=MAX_NPIS_DICT)

        # Check it
        self._check_future(start_date_str=None,
                           end_date_str=end_date_str,
                           scenario_df=scenario_df,
                           scenario_npis=scenario[0],
                           country=countries[0])

    def test_generate_scenario_all_countries_future_from_last_known_date_freeze(self):
        # Simulate ALL countries uses custom NPIs for 1 week after last known date
        countries = None

        # Set end date to 1 week from last known date
        last_known_date = self.latest_df.Date.max()
        end_date_str = (last_known_date + pd.DateOffset(7)).strftime(DATE_FORMAT)

        # Make sure we generate scenarios for enough days
        official_end_date_str = "2022-12-01"
        official_end_date = pd.to_datetime(official_end_date_str, format=DATE_FORMAT)
        nb_days = (last_known_date - official_end_date).days
        scenario = [ONE_NPIS] * nb_days

        # Generate the scenarios
        scenario_df = generate_scenario(None,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario=scenario,
                                        max_npis_dict=MAX_NPIS_DICT)

        # Check them
        all_countries = self.latest_df.CountryName.unique()
        for country in all_countries:
            all_regions = self.latest_df[self.latest_df.CountryName == country].RegionName.unique()
            for region in all_regions:
                self._check_future(start_date_str=None,
                                   end_date_str=end_date_str,
                                   scenario_df=scenario_df[(scenario_df.CountryName == country) &
                                                           (scenario_df.RegionName == region)],
                                   scenario_npis=scenario[0],
                                   country=country,
                                   region=region)

    def _check_future(self, start_date_str, end_date_str, scenario_df, scenario_npis, country, region=""):
        self.assertIsNotNone(scenario_df)
        # Misleading name but checks the elements, regardless of order
        self.assertCountEqual([country], scenario_df.CountryName.unique(), "Not the expected country")
        self.assertCountEqual([region], scenario_df.RegionName.unique(), "Not the requested region")
        self.assertFalse(scenario_df["Date"].duplicated().any(), "Expected 1 row per date only")
        end_date = pd.to_datetime(end_date_str, format=DATE_FORMAT)

        # Check the "historical" period
        last_known_date = self.latest_df[(self.latest_df.CountryName == country) &
                                         (self.latest_df.RegionName == region)].Date.max()
        # If the start date is not specified, start from the day after the last known day
        if not start_date_str:
            start_date = last_known_date + np.timedelta64(1, 'D')
        else:
            start_date = pd.to_datetime(start_date_str, format=DATE_FORMAT)
        past_df = scenario_df[scenario_df.Date < start_date][NPI_COLUMNS].reset_index(drop=True)
        historical_df = self.latest_df[(self.latest_df.CountryName == country) &
                                       (self.latest_df.RegionName == region) &
                                       (self.latest_df.Date < start_date)][NPI_COLUMNS].reset_index(drop=True)
        pd.testing.assert_frame_equal(historical_df, past_df, "Not the expected past NPIs")

        # Check the "future" period (+1 to include start and end date)
        nb_days = (end_date - start_date).days + 1
        for i in range(nb_days):
            check_day = start_date + np.timedelta64(i, 'D')
            self.assertFalse(scenario_df[scenario_df.Date == check_day].empty,
                             f"Expected npis for country {country}, region {region}, day {check_day}")
            check_day_npis_df = scenario_df[scenario_df.Date == check_day][NPI_COLUMNS].reset_index(drop=True)
            check_day_npis = list(check_day_npis_df.values[0])
            self.assertListEqual(scenario_npis, check_day_npis)

        # Check last day is indeed end_date
        self.assertEqual(end_date, scenario_df.tail(1).Date.values[0], "Not the expected end date")

    def test_generate_scenario_mind_the_gap_freeze(self):
        # Scenario = Freeze
        nb_days = 31
        countries = ["Italy"]
        last_known_date = self.latest_df[self.latest_df.CountryName == countries[0]].Date.max()
        start_date = last_known_date + timedelta(days=7)
        start_date_str = start_date.strftime(DATE_FORMAT)
        end_date = start_date + timedelta(days=nb_days)
        end_date_str = end_date.strftime(DATE_FORMAT)
        inception_date = pd.to_datetime(INCEPTION_DATE, format=DATE_FORMAT)

        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario="Freeze",
                                        max_npis_dict=MAX_NPIS_DICT)
        self.assertIsNotNone(scenario_df)
        # Misleading name but checks the elements, regardless of order
        self.assertCountEqual(countries, scenario_df.CountryName.unique(), "Not the requested countries")
        # Check we get the expected number of days
        expected_days = (end_date - inception_date).days + 1  # +1 because inception_date and end_date are included
        self.assertEqual(expected_days, len(scenario_df), "Expected the number of days between inception and end date")
        # The last nb_days rows must be the same
        self.assertEqual(0, scenario_df.tail(nb_days)[NPI_COLUMNS].diff().sum().sum(),
                         f"Expected the last {nb_days} rows to have the same frozen IP")

    def test_generate_scenario_mind_the_gap_min(self):
        # Scenario = MIN
        nb_days = 31
        countries = ["Italy"]
        last_known_date = self.latest_df[self.latest_df.CountryName == countries[0]].Date.max()
        start_date = last_known_date + timedelta(days=7)
        start_date_str = start_date.strftime(DATE_FORMAT)
        end_date = start_date + timedelta(days=nb_days)
        end_date_str = end_date.strftime(DATE_FORMAT)
        inception_date = pd.to_datetime(INCEPTION_DATE, format=DATE_FORMAT)

        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario="MIN",
                                        max_npis_dict=MAX_NPIS_DICT)
        self.assertIsNotNone(scenario_df)
        # Misleading name but checks the elements, regardless of order
        self.assertCountEqual(countries, scenario_df.CountryName.unique(), "Not the requested countries")
        # Check we get the expected number of days
        expected_days = (end_date - inception_date).days + 1  # +1 because inception_date and end_date are included
        self.assertEqual(expected_days, len(scenario_df), "Expected the number of days between inception and end date")
        # The last nb_days rows must be the same
        self.assertEqual(0, scenario_df.tail(nb_days)[NPI_COLUMNS].sum().sum(),
                         f"Expected the last {nb_days} rows to have NPIs set to 0")

    def test_generate_scenario_mind_the_gap_max(self):
        # Scenario = MAX
        nb_days = 31
        countries = ["Italy"]
        last_known_date = self.latest_df[self.latest_df.CountryName == countries[0]].Date.max()
        start_date = last_known_date + timedelta(days=7)
        start_date_str = start_date.strftime(DATE_FORMAT)
        end_date = start_date + timedelta(days=nb_days)
        end_date_str = end_date.strftime(DATE_FORMAT)
        inception_date = pd.to_datetime(INCEPTION_DATE, format=DATE_FORMAT)

        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario="MAX",
                                        max_npis_dict=MAX_NPIS_DICT)
        self.assertIsNotNone(scenario_df)
        # Misleading name but checks the elements, regardless of order
        self.assertCountEqual(countries, scenario_df.CountryName.unique(), "Not the requested countries")
        # Check we get the expected number of days
        expected_days = (end_date - inception_date).days + 1  # +1 because inception_date and end_date are included
        self.assertEqual(expected_days, len(scenario_df), "Expected the number of days between inception and end date")
        # The last nb_days rows must be the same
        self.assertEqual(sum(MAX_NPIS), scenario_df.tail(nb_days)[NPI_COLUMNS].mean().sum(),
                         f"Expected the last {nb_days} rows to have NPIs set to their max value")

    def test_generate_scenario_mind_the_gap_custom(self):
        # Scenario = Custom
        nb_days = 31
        start_lag = 7
        countries = ["Italy"]
        last_known_date = self.latest_df[self.latest_df.CountryName == countries[0]].Date.max()
        start_date = last_known_date + timedelta(days=start_lag)
        start_date_str = start_date.strftime(DATE_FORMAT)
        end_date = start_date + timedelta(days=nb_days)
        end_date_str = end_date.strftime(DATE_FORMAT)
        inception_date = pd.to_datetime(INCEPTION_DATE, format=DATE_FORMAT)

        # Set all the NPIs to one for each day between start date and end date, as well as from last known date.
        scenario = [ONE_NPIS] * (nb_days + start_lag)
        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario=scenario,
                                        max_npis_dict=MAX_NPIS_DICT)
        self.assertIsNotNone(scenario_df)
        # Misleading name but checks the elements, regardless of order
        self.assertCountEqual(countries, scenario_df.CountryName.unique(), "Not the requested countries")
        # Check we get the expected number of days
        expected_days = (end_date - inception_date).days + 1  # +1 because inception_date and end_date are included
        self.assertEqual(expected_days, len(scenario_df), "Expected the number of days between inception and end date")
        # The last 31 rows must be the same
        self.assertEqual(1, scenario_df.tail(nb_days)[NPI_COLUMNS].mean().mean(),
                         f"Expected the last {nb_days} rows to have all NPIs set to 1")

    def test_generate_scenario_mind_the_gap_freeze_2_countries(self):
        # Check 2 countries
        nb_days = 31
        # We have 2 countries, and they may have different last know dates.
        # Set start date to 7 days from now to guarantee a gap
        start_date = datetime.now() + timedelta(days=7)
        start_date_str = start_date.strftime(DATE_FORMAT)
        end_date = start_date + timedelta(days=nb_days)
        end_date_str = end_date.strftime(DATE_FORMAT)
        inception_date = pd.to_datetime(INCEPTION_DATE, format=DATE_FORMAT)

        countries = ["France", "Italy"]
        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario="Freeze",
                                        max_npis_dict=MAX_NPIS_DICT)
        self.assertIsNotNone(scenario_df)
        # Misleading name but checks the elements, regardless of order
        self.assertCountEqual(countries, scenario_df.CountryName.unique(), "Not the requested countries")
        # Check we get the expected number of days
        expected_days = (end_date - inception_date).days + 1  # +1 because inception_date and end_date are included
        self.assertEqual(expected_days * 2, len(scenario_df),
                         "Not the expected number of days between inception and end date")

    def test_generate_scenario_mind_the_gap_freeze_all_countries(self):
        # Check all countries, with frozen npis for 180 days, 1 week from today
        start_date = datetime.now() + timedelta(days=7)
        start_date_str = start_date.strftime(DATE_FORMAT)
        end_date = start_date + timedelta(days=180)
        end_date_str = end_date.strftime(DATE_FORMAT)
        inception_date = datetime.strptime(INCEPTION_DATE, DATE_FORMAT)
        countries = None
        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        self.latest_df,
                                        countries,
                                        scenario="Freeze",
                                        max_npis_dict=MAX_NPIS_DICT)
        self.assertIsNotNone(scenario_df)
        nb_days_since_inception = (end_date - inception_date).days + 1
        # For each country, assert the scenario contains the expected number of days
        for country in self.latest_df.CountryName.unique():
            all_regions = self.latest_df[self.latest_df.CountryName == country].RegionName.unique()
            for region in all_regions:
                ips_gdf = scenario_df[(scenario_df.CountryName == country) &
                                      (scenario_df.RegionName == region)]
                self.assertEqual(nb_days_since_inception, len(ips_gdf), f"Not the expected number of days"
                                                                        f" for {country} / {region}")

    def test_generate_scenario_mind_the_gap_freeze_dates_mismatch(self):
        # Check scenario contains all days, for 2 countries, where 1 country has 1 more day of data than the other
        # Last known date:
        # - Belgium: 20201103
        # - Brazil:  20201104
        # Make sure we don't skip a day
        start_date_str = "2021-01-01"
        end_date_str = "2021-01-31"
        countries = ["Belgium", "Brazil"]
        dates_mismatch_df = get_raw_data(DATES_MISMATCH_DATA_FILE, latest=False)
        # Not specifying NPIs: can only test the 'default' NPIs that are in DATES_MISMATCH_DATA_FILE
        scenario_df = generate_scenario(start_date_str,
                                        end_date_str,
                                        dates_mismatch_df,
                                        countries,
                                        scenario="Freeze")
        self.assertIsNotNone(scenario_df)
        # Misleading name but checks the elements, regardless of order
        self.assertCountEqual(countries, scenario_df.CountryName.unique(), "Not the requested countries")
        # Inception is 2020-01-01. 366 days for 2020 + 31 for Jan 2021
        nb_days_since_inception = 397
        # For each country, assert the scenario contains the expected number of days
        for country in countries:
            all_regions = dates_mismatch_df[dates_mismatch_df.CountryName == country].RegionName.unique()
            for region in all_regions:
                ips_gdf = scenario_df[(scenario_df.CountryName == country) & (scenario_df.RegionName == region)]
                self.assertEqual(nb_days_since_inception, len(ips_gdf), f"Not the expected number of days"
                                                                        f" for {country} / {region}")
