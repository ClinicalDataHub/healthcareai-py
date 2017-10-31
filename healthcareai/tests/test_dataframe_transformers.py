import unittest
import string
import random

import pandas as pd
import numpy as np

import healthcareai.common.transformers as transformers


def _convert_all_columns_to_uint8(df, ignore=None):
    # pandas.get_dummies() outputs uint8
    if not isinstance(ignore, list):
        ignore = [ignore]

    # filtered_df = df[df.columns.difference(ignore)]
    for col in df:
        if col in ignore:
            df[col] = df[col]
        else:
            df[col] = df[col].astype('uint8')

    return df


def _assert_dataframes_identical(expected, result):
    """
    Asserts dataframes are identical in many ways.

    1. Sort each because column order matters for equality checks
    2. Check that column names are identical
    3. Check each series is identical
    4. Check the entire dataframe
    """
    expected = expected.sort_index(axis=1)
    result = result.sort_index(axis=1)

    test_case = unittest.TestCase()

    test_case.assertListEqual(list(expected.columns), list(result.columns))

    for col in expected:
        pd.testing.assert_series_equal(expected[col], result[col])

    test_case.assertTrue(list(expected.dtypes) == list(result.dtypes))

    pd.testing.assert_frame_equal(
        expected, result,
        check_dtype=True,
        check_index_type=True,
        check_column_type=True,
        check_frame_type=True,
        check_exact=True,
        check_names=True,
        check_datetimelike_compat=True,
        check_categorical=True,
        check_like=True)


class TestDataframeImputer(unittest.TestCase):
    def test_false_returns_unmodified(self):
        df = pd.DataFrame([
            ['a', 1, 2],
            ['b', 1, 1],
            ['b', 2, 2],
            ['a', None, None]
        ])
        expected = pd.DataFrame([
            ['a', 1, 2],
            ['b', 1, 1],
            ['b', 2, 2],
            ['a', None, None]
        ])

        result = transformers.DataFrameImputer(impute=False).fit_transform(df)

        self.assertEqual(len(result), 4)
        _assert_dataframes_identical(expected, result)

    def test_removes_nans(self):
        df = pd.DataFrame([
            ['a', 1, 2],
            ['b', 1, 1],
            ['b', 2, 2],
            [np.nan, np.nan, np.nan]
        ])
        expected = pd.DataFrame([
            ['a', 1, 2],
            ['b', 1, 1],
            ['b', 2, 2],
            ['b', 4 / 3.0, 5 / 3.0]
        ])

        result = transformers.DataFrameImputer().fit_transform(df)

        self.assertEqual(len(result), 4)
        # Assert no NANs
        self.assertFalse(result.isnull().values.any())
        _assert_dataframes_identical(expected, result)

    def test_removes_nones(self):
        df = pd.DataFrame([
            ['a', 1, 2],
            ['b', 1, 1],
            ['b', 2, 2],
            [None, None, None]
        ])
        expected = pd.DataFrame([
            ['a', 1, 2],
            ['b', 1, 1],
            ['b', 2, 2],
            ['b', 4 / 3.0, 5 / 3.0]
        ])

        result = transformers.DataFrameImputer().fit_transform(df)
        self.assertEqual(len(result), 4)
        self.assertFalse(result.isnull().values.any())

        _assert_dataframes_identical(expected, result)

    def test_for_mean_of_numeric_and_mode_for_object(self):
        df = pd.DataFrame([
            ['a', 1, 2],
            ['b', 1, 1],
            ['b', 2, 2],
            [None, None, None]
        ])

        result = transformers.DataFrameImputer().fit_transform(df)

        expected = pd.DataFrame([
            ['a', 1, 2],
            ['b', 1, 1],
            ['b', 2, 2],
            ['b', 4. / 3, 5. / 3]
        ])

        self.assertEqual(len(result), 4)

        _assert_dataframes_identical(expected, result)


class TestDataFrameConvertTargetToBinary(unittest.TestCase):
    def test_does_nothing_on_regression(self):
        expected = pd.DataFrame({
            'category': ['a', 'b', 'c'],
            'gender': ['F', 'M', 'F'],
            'outcome': [1, 5, 4],
            'string_outcome': ['Y', 'N', 'Y']
        })

        result = transformers.DataFrameConvertTargetToBinary('regression', 'string_outcome').fit_transform(expected)

        _assert_dataframes_identical(expected, result)

    def test_converts_y_n_for_classification(self):
        df = pd.DataFrame({
            'category': ['a', 'b', 'c'],
            'gender': ['F', 'M', 'F'],
            'outcome': [1, 5, 4],
            'string_outcome': ['Y', 'N', 'Y']
        })

        expected = pd.DataFrame({
            'category': ['a', 'b', 'c'],
            'gender': ['F', 'M', 'F'],
            'outcome': [1, 5, 4],
            'string_outcome': [1, 0, 1]
        })

        result = transformers.DataFrameConvertTargetToBinary('classification', 'string_outcome').fit_transform(df)

        _assert_dataframes_identical(expected, result)


class TestDataFrameCreateDummyVariables(unittest.TestCase):
    def setUp(self):
        row_count = 100

        # Build an array of the alphabet repeated up to n elements
        self.alphabet = list(list(string.ascii_lowercase) * 100)
        del self.alphabet[row_count:]

        # build a dataframe with a object and category types
        self.train_df = pd.DataFrame({
            'id': range(row_count),
            'binary': np.random.choice(['a', 'b'], row_count, p=[.75, .25]),
            'alphabet': self.alphabet,
            'numeric': random.sample(range(0, row_count), row_count),
            'color': np.random.choice(
                ['red', 'green', 'blue'],
                row_count,
                p=[.1, .6, .3])
        })

        # Create a few categorical columns from object columns to ensure that
        # both types work
        self.train_df['binary_cat'] = self.train_df['binary'].astype('category')
        self.train_df['binary'] = self.train_df['binary'].astype(
            'category',
            categories=['a', 'b'])
        self.train_df['color_cat'] = self.train_df['color'].astype(
            'category',
            categories=['red', 'green', 'blue'])

        # sanity check that 'green' is the most common color
        self.assertEqual(self.train_df['color_cat'].value_counts().index[0], 'green')

        self.dummifier = transformers.DataFrameCreateDummyVariables('id').fit(self.train_df)

    def test_binary_object_and_category(self):
        df = pd.DataFrame({
            'id': [1, 5, 4],
            'binary': ['a', 'b', 'a'],
            'binary_cat': ['a', 'b', 'a'],
            'numeric': [1, 2, 1],
        })
        df['binary_cat'] = df['binary_cat'].astype('category')

        expected = pd.DataFrame({
            'id': [1, 5, 4],
            'binary.b': [0, 1, 0],
            'binary_cat.b': [0, 1, 0],
            'numeric': [1, 2, 1],
        })
        # cast as uint8 which the pandas.get_dummies() outputs
        expected = expected.astype({
            'binary.b': 'uint8',
            'binary_cat.b': 'uint8',
        })

        fit_dummifier = transformers.DataFrameCreateDummyVariables(
            'id').fit(df)

        result = fit_dummifier.transform(df)

        _assert_dataframes_identical(expected, result)

    def test_three_object_and_category(self):
        df = pd.DataFrame({
            'trinary': ['a', 'b', 'c'],
            'trinary_cat': ['a', 'b', 'c'],
            'id': [1, 5, 4]})
        df.trinary_cat = df.trinary_cat.astype('category')

        expected = pd.DataFrame({
            'id': [1, 5, 4],
            'trinary.b': [0, 1, 0],
            'trinary.c': [0, 0, 1],
            'trinary_cat.b': [0, 1, 0],
            'trinary_cat.c': [0, 0, 1]})

        # cast as uint8 which the pandas.get_dummies() outputs
        expected = expected.astype({
            'trinary.b': 'uint8',
            'trinary.c': 'uint8',
            'trinary_cat.b': 'uint8',
            'trinary_cat.c': 'uint8'})

        result = transformers.DataFrameCreateDummyVariables(
            'id').fit_transform(df)

        _assert_dataframes_identical(expected, result)

    def test_remembers_unrepresented_categories(self):
        prediction_df = pd.DataFrame({
            'id': [1, 5, 4],
            'binary': ['a', 'a', 'a'],
            'binary_cat': ['a', 'a', 'a'],
            'numeric': [1, 2, 1],
        })
        prediction_df['binary_cat'] = prediction_df['binary_cat'].astype('category')

        expected = pd.DataFrame({
            'id': [1, 5, 4],
            'binary.b': [0, 0, 0],
            'binary_cat.b': [0, 0, 0],
            'numeric': [1, 2, 1],
        })
        # cast as uint8 which the pandas.get_dummies() outputs
        expected = expected.astype({
            'binary.b': 'uint8',
            'binary_cat.b': 'uint8'})

        trained = transformers.DataFrameCreateDummyVariables('id').fit(self.train_df)
        result = trained.transform(prediction_df)

        _assert_dataframes_identical(expected, result)

    def test_none_represented(self):
        prediction_df = pd.DataFrame({
            'id': [1, 5, 4],
            'binary': ['a', 'a', 'a'],
            'alphabet': [None, None, None],
            'numeric': [1, 2, 1],
        })

        expected = pd.DataFrame({
            'id': [1, 5, 4],
            'binary.b': [0, 0, 0],
            'alphabet.b': [0, 0, 0],
            'alphabet.c': [0, 0, 0],
            'alphabet.d': [0, 0, 0],
            'alphabet.e': [0, 0, 0],
            'alphabet.f': [0, 0, 0],
            'alphabet.g': [0, 0, 0],
            'alphabet.h': [0, 0, 0],
            'alphabet.i': [0, 0, 0],
            'alphabet.j': [0, 0, 0],
            'alphabet.k': [0, 0, 0],
            'alphabet.l': [0, 0, 0],
            'alphabet.m': [0, 0, 0],
            'alphabet.n': [0, 0, 0],
            'alphabet.o': [0, 0, 0],
            'alphabet.p': [0, 0, 0],
            'alphabet.q': [0, 0, 0],
            'alphabet.r': [0, 0, 0],
            'alphabet.s': [0, 0, 0],
            'alphabet.t': [0, 0, 0],
            'alphabet.u': [0, 0, 0],
            'alphabet.v': [0, 0, 0],
            'alphabet.w': [0, 0, 0],
            'alphabet.x': [0, 0, 0],
            'alphabet.y': [0, 0, 0],
            'alphabet.z': [0, 0, 0],
            'numeric': [1, 2, 1],
        })

        expected = _convert_all_columns_to_uint8(expected, ['id', 'numeric'])
        result = self.dummifier.transform(prediction_df)

        _assert_dataframes_identical(expected, result)

    def test_get_unseen_factors(self):
        """binary column is as expected and alphabet column has new levels."""
        prediction_df = pd.DataFrame({
            'id': [1, 5, 4],
            'binary': ['a', 'b', 'a'],
            'alphabet': ['Zebra', 'r', 'Automaton'],
            'numeric': [1, 2, 1],
        })

        unseen_by_column = {
            'binary': set(),
            'alphabet': {'Zebra', 'Automaton'}}

        for col, expected in unseen_by_column.items():
            result = self.dummifier._get_unseen_factors(prediction_df, col)
            self.assertIsInstance(result, set)
            self.assertEqual(expected, result)

    def test_get_unrepresented_factors(self):
        prediction_df = pd.DataFrame({
            'id': [1, 5, 4],
            'binary': ['a', 'a', 'a'],
            'alphabet': ['a', 'b', 'c'],
            'numeric': [1, 2, 1],
        })

        partial_alphabet = set(string.ascii_lowercase) - {'a', 'b', 'c'}

        unrepresented_by_column = {
            'binary': {'b'},
            'alphabet': partial_alphabet}

        for col, expected in unrepresented_by_column.items():
            result = self.dummifier._get_unrepresented_factors(prediction_df, col)
            self.assertIsInstance(result, set)
            self.assertEqual(expected, result)

    def test_get_expected_factors_set(self):
        expected = {
            'binary': {'a', 'b'},
            'binary_cat': {'a', 'b'},
            'alphabet': set(list(string.ascii_lowercase)),
            'color': {'red', 'green', 'blue'},
            'color_cat': {'red', 'green', 'blue'},
        }

        for col in self.train_df.select_dtypes(['category', object]):
            result = self.dummifier._get_expected_factors_set(col)
            self.assertIsInstance(result, set)
            self.assertEqual(expected[col], result)

    def test_get_unique_factors_set(self):
        expected = {
            'binary': {'a', 'b'},
            'binary_cat': {'a', 'b'},
            'alphabet': set(list(string.ascii_lowercase)),
            'color': {'red', 'green', 'blue'},
            'color_cat': {'red', 'green', 'blue'},
        }

        for col in self.train_df.select_dtypes(['category', object]):
            result = self.dummifier._get_unique_factors_set(self.train_df, col)
            self.assertIsInstance(result, set)
            self.assertEqual(expected[col], result)

    def test_calculate_found_and_expected_factors(self):
        prediction_df = pd.DataFrame({
            'id': [1, 5, 4, 99],
            'binary': ['a', 'a', 'a', 'UNSEEN'],
            'binary_cat': ['a', 'a', 'a', 'UNSEEN'],
            'alphabet': ['a', 'b', 'c', 'Zebra'],
            'numeric': [1, 2, 1, 3],
            'color': ['red', 'red', 'blue', 'SILVER_UNSEEN'],
            'color_cat': ['red', 'red', 'blue', 'SILVER_UNSEEN'],
        })
        prediction_df = prediction_df.astype({
            'binary_cat': 'category',
            'color_cat': 'category',
        })

        expected_expected_by_column = {
            'binary': {'a', 'b'},
            'binary_cat': {'a', 'b'},
            'alphabet': set(list(string.ascii_lowercase)),
            'color': {'red', 'green', 'blue'},
            'color_cat': {'red', 'green', 'blue'},
        }

        expected_found_by_column = {
            'binary': {'a', 'UNSEEN'},
            'binary_cat': {'a', 'UNSEEN'},
            'alphabet': {'a', 'b', 'c', 'Zebra'},
            'color': {'red', 'blue', 'SILVER_UNSEEN'},
            'color_cat': {'red', 'blue', 'SILVER_UNSEEN'},
        }

        for col in self.train_df.select_dtypes(['category', object]):
            result_expected, result_found = self.dummifier._calculate_found_and_expected_factors(prediction_df, col)
            self.assertIsInstance(result_expected, set)
            self.assertIsInstance(result_found, set)
            self.assertEqual(expected_expected_by_column[col], result_expected)
            self.assertEqual(expected_found_by_column[col], result_found)

    def test_remembers_all_unrepresented_categories(self):
        prediction_df = pd.DataFrame({
            'id': [1, 5, 4],
            'binary': ['a', 'a', 'a'],
            'alphabet': ['t', 'r', 'y'],
            'numeric': [1, 2, 1],
        })

        expected = pd.DataFrame({
            'id': [1, 5, 4],
            'binary.b': [0, 0, 0],
            'alphabet.b': [0, 0, 0],
            'alphabet.c': [0, 0, 0],
            'alphabet.d': [0, 0, 0],
            'alphabet.e': [0, 0, 0],
            'alphabet.f': [0, 0, 0],
            'alphabet.g': [0, 0, 0],
            'alphabet.h': [0, 0, 0],
            'alphabet.i': [0, 0, 0],
            'alphabet.j': [0, 0, 0],
            'alphabet.k': [0, 0, 0],
            'alphabet.l': [0, 0, 0],
            'alphabet.m': [0, 0, 0],
            'alphabet.n': [0, 0, 0],
            'alphabet.o': [0, 0, 0],
            'alphabet.p': [0, 0, 0],
            'alphabet.q': [0, 0, 0],
            'alphabet.r': [0, 1, 0],
            'alphabet.s': [0, 0, 0],
            'alphabet.t': [1, 0, 0],
            'alphabet.u': [0, 0, 0],
            'alphabet.v': [0, 0, 0],
            'alphabet.w': [0, 0, 0],
            'alphabet.x': [0, 0, 0],
            'alphabet.y': [0, 0, 1],
            'alphabet.z': [0, 0, 0],
            'numeric': [1, 2, 1],
        })

        expected = _convert_all_columns_to_uint8(expected, ['id', 'numeric'])

        result = self.dummifier.transform(prediction_df)

        _assert_dataframes_identical(expected, result)


class TestDataFrameConvertColumnToNumeric(unittest.TestCase):
    def test_integer_strings(self):
        df = pd.DataFrame({
            'integer_strings': ['1', '2', '3'],
            'binary_category': ['a', 'b', 'a'],
            'numeric': [1, 2, 1],
        })
        expected = pd.DataFrame({
            'integer_strings': [1, 2, 3],
            'binary_category': ['a', 'b', 'a'],
            'numeric': [1, 2, 1],
        })

        result = transformers.DataFrameConvertColumnToNumeric('integer_strings').fit_transform(df)
        _assert_dataframes_identical(expected, result)

    def test_integer(self):
        df = pd.DataFrame({
            'binary_category': ['a', 'b', 'a'],
            'numeric': [1, 2, 1],
        })
        expected = pd.DataFrame({
            'binary_category': ['a', 'b', 'a'],
            'numeric': [1, 2, 1],
        })

        result = transformers.DataFrameConvertColumnToNumeric('numeric').fit_transform(df)

        _assert_dataframes_identical(expected, result)


class TestDataframeUnderSampler(unittest.TestCase):
    def setUp(self):
        # Build an imbalanced dataframe (20% True at_risk)
        self.df = pd.DataFrame({'id': [1, 2, 3, 4, 5, 6, 7, 8],
                                'is_male': [1, 0, 1, 0, 0, 0, 1, 1],
                                'height': [100, 80, 70, 85, 100, 80, 70, 85],
                                'weight': [99, 46, 33, 44, 99, 46, 33, 44],
                                'at_risk': [True, False, False, False, True, False, False, False],
                                })

        self.result = transformers.DataFrameUnderSampling('at_risk', random_seed=42).fit_transform(self.df)

    def test_returns_dataframe(self):
        self.assertTrue(isinstance(self.result, pd.DataFrame))

    def test_returns_smaller_dataframe(self):
        self.assertLess(len(self.result), len(self.df))

    def test_returns_balanced_classes(self):
        # For sanity, verify that the original classes were imbalanced
        original_value_counts = self.df['at_risk'].value_counts()
        original_true_count = original_value_counts[1]
        original_false_count = original_value_counts[0]

        self.assertNotEqual(original_true_count, original_false_count)

        # Verify that the new classes are balanced
        value_counts = self.result['at_risk'].value_counts()
        true_count = value_counts[1]
        false_count = value_counts[0]

        self.assertEqual(true_count, false_count)


class TestDataframeOverSampler(unittest.TestCase):
    def setUp(self):
        # Build an imbalanced dataframe (20% True at_risk)
        self.df = pd.DataFrame({'id': [1, 2, 3, 4, 5, 6, 7, 8],
                                'is_male': [1, 0, 1, 0, 0, 0, 1, 1],
                                'height': [100, 80, 70, 85, 100, 80, 70, 85],
                                'weight': [99, 46, 33, 44, 99, 46, 33, 44],
                                'at_risk': [True, False, False, False, True, False, False, False],
                                })

        self.result = transformers.DataFrameOverSampling('at_risk', random_seed=42).fit_transform(self.df)

    def test_returns_dataframe(self):
        self.assertTrue(isinstance(self.result, pd.DataFrame))

    def test_returns_larger_dataframe(self):
        self.assertGreater(len(self.result), len(self.df))

    def test_returns_balanced_classes(self):
        # For sanity, verify that the original classes were imbalanced
        original_value_counts = self.df['at_risk'].value_counts()
        original_true_count = original_value_counts[1]
        original_false_count = original_value_counts[0]

        self.assertNotEqual(original_true_count, original_false_count)

        # Verify that the new classes are balanced
        value_counts = self.result['at_risk'].value_counts()
        true_count = value_counts[1]
        false_count = value_counts[0]

        self.assertEqual(true_count, false_count)


class TestRemovesNANs(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            'a': [1, None, 2, 3, None],
            'b': ['m', 'f', None, 'f', None],
            'c': [3, 4, 5, None, None],
            'd': [None, 8, 1, 3, None],
            'e': [None, None, None, None, None],
            'label': ['Y', 'N', 'Y', 'N', None]})

    def test_removes_nan_rows(self):
        result = transformers.DataFrameDropNaN().fit_transform(self.df)
        expected = pd.DataFrame(
            {'a': [1, None, 2, 3, None],
             'b': ['m', 'f', None, 'f', None],
             'c': [3, 4, 5, None, None],
             'd': [None, 8, 1, 3, None],
             'label': ['Y', 'N', 'Y', 'N', None]})
        _assert_dataframes_identical(expected, result)


class TestFeatureScaling(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame({
            'a': [1, 3, 2, 3],
            'b': ['m', 'f', 'b', 'f'],
            'c': [3, 4, 5, 5],
            'd': [6, 8, 1, 3],
            'label': ['Y', 'N', 'Y', 'N']})

        self.df_repeat = pd.DataFrame({
            'a': [1, 3, 2, 3],
            'b': ['m', 'f', 'b', 'f'],
            'c': [3, 4, 5, 5],
            'd': [6, 8, 1, 3],
            'label': ['Y', 'N', 'Y', 'N']})

    def runTest(self):
        expected = pd.DataFrame({
            'a': [-1.507557, 0.904534, -0.301511, 0.904534],
            'b': ['m', 'f', 'b', 'f'],
            'c': [-1.507557, -0.301511, 0.904534, 0.904534],
            'd': [0.557086, 1.299867, -1.299867, -0.557086],
            'label': ['Y', 'N', 'Y', 'N']})

        feature_scaling = transformers.DataFrameFeatureScaling()
        df_final = feature_scaling.fit_transform(self.df).round(5)

        _assert_dataframes_identical(expected.round(5), df_final)

        df_reused = transformers.DataFrameFeatureScaling(reuse=feature_scaling).fit_transform(self.df_repeat).round(5)
        _assert_dataframes_identical(expected.round(5), df_reused)


if __name__ == '__main__':
    unittest.main()
