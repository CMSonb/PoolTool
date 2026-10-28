import unittest

from time_mapping import parse_time

# (Eingabe, begin_year, end_year, iso, method)
CASES = [
    ("1855-1861", 1855, 1861, "1855/1861", "rule"),
    ("0085 - 0180", 85, 180, "0085/0180", "rule"),
    ("100 n. Chr. - 200 n. Chr.", 100, 200, "0100/0200", "rule"),
    ("70 n. Chr. - 100 n. Chr. (Flavisch)", 70, 100, "0070/0100", "rule"),
    ("um 2000 v. Chr.-1600 v. Chr.", -2000, -1600, "-1999~/-1599~", "rule"),
    ("5. Jh. v. Chr.", -500, -401, "-0499/-0400", "rule"),
    ("19. Jh. (?)", 1801, 1900, "1801?/1900?", "rule"),
    ("Ende 19. Jh.", 1867, 1900, "1867/1900", "rule"),
    ("2. Hälfte 19. Jh.", 1851, 1900, "1851/1900", "rule"),
    ("18. - 19. Jh. (?)", 1701, 1900, "1701?/1900?", "rule"),
    ("19./20. Jahrhundert", 1801, 2000, "1801/2000", "rule"),
    ("um 1100", 1100, 1100, "1100~", "rule"),
    ("1900, ca.- 1930, ca.", 1900, 1930, "1900~/1930~", "rule"),
    ("13.06.1987", 1987, 1987, "1987-06-13", "rule"),
    ("2024-01-31", 2024, 2024, "2024-01-31", "rule"),
    ("12.1936", 1936, 1936, "1936-12", "rule"),
    ("Mai 1964", 1964, 1964, "1964-05", "rule"),
    ("1939/1945", 1939, 1945, "1939/1945", "rule"),
    ("24.01.1986, 25.01.1986", 1986, 1986, "1986-01-24/1986-01-25", "rule"),
    ("1470-", 1470, None, "1470/..", "rule"),
    ("nach 1945", 1945, None, "1945/..", "rule"),
    ("[vor oder im Jahr 1905]", None, 1905, "../1905", "rule"),
    ("1330.0", 1330, 1330, "1330", "rule"),
    ("[1845]", 1845, 1845, "1845", "rule"),
    ("Römische Kaiserzeit (-15-476)", -15, 476, "-0014/0476", "rule_label_range"),
    ("13. Jahrhundert (1201-1300)", 1201, 1300, "1201/1300", "rule_label_range"),
    ("1. Viertel 17. Jh.", 1601, 1625, "1601/1625", "rule"),
    ("Erste Hälfte 20. Jh. (?)", 1901, 1950, "1901?/1950?", "rule"),
    ("Ende 20. - Anfang 21 Jh. (?)", 1967, 2033, "1967?/2033?", "rule"),
    ("[1930er Jahre]", 1930, 1939, "1930/1939", "rule"),
    ("ab 1964", 1964, None, "1964/..", "rule"),
    ("1936 bis 1975", 1936, 1975, "1936/1975", "rule"),
    ("30.09.1987, 01., 03., 04.10.1987", 1987, 1987, "1987-09-30/1987-10-04", "rule"),
    ("08.08.1987, 08.\u201318.08.1987", 1987, 1987, "1987-08-08/1987-08-18", "rule"),
    ("1933.03.xx", 1933, 1933, "1933-03", "rule"),
    ("vermutlich 1903", 1903, 1903, "1903?", "rule"),
    ("01: 1952;\n02: 1951", 1951, 1952, "1951/1952", "rule"),
    ("Poststempel: Augsburg, 13.03.1978", 1978, 1978, "1978-03-13", "rule_embedded"),
    ("Neuzeit", 1500, None, "1500/..", "table"),
    ("Modern", 1900, None, "1900/..", "table"),
    ("Romantik", 1790, 1850, "1790/1850", "table"),
    ("Minoan | Minoisch", -3500, -1050, "-3499/-1049", "table"),
    ("ca. 50 v. Chr.-50", -50, 50, "-0049~/0050~", "table"),
    ("-60000000", -60000000, -60000000, "Y-60000000", "table"),
    ("X", None, None, "", "no_date"),
    ("2 Hälfte des 19. Jhdt.", 1851, 1900, "1851/1900", "rule"),
    ("-125000 - -19650", -125000, -19650, "Y-125000/Y-19650", "rule"),
    ("zwischen 1950 und 1997", 1950, 1997, "1950/1997", "rule"),
    ("Aufgenommen in Sri Lanka zwischen 1950 und 1997", 1950, 1997, "1950/1997", "rule_embedded"),
    ("1 (1914)-5 (1917)", 1914, 1917, "1914/1917", "rule_embedded"),
    ("1906, ca. 1970 (Eintragungen)", 1906, 1970, "1906~/1970~", "rule"),
    ("1967\nAngabe laut Verpackung: 1972", 1967, 1972, "1967/1972", "rule_embedded"),
    ("Anfang 18. Jh. / Ergänzungen 20. Jh.", 1701, 1733, "1701/1733", "rule"),
    ("1809-9999", 1809, None, "1809/..", "rule"),
    ("[1809?]", 1809, 1809, "1809?", "rule"),
    ("Geschichte", None, None, "", "no_date"),
    ("div.", None, None, "", "no_date"),
    ("Phanerozoic | Cenozoic | Neogene | Miocene (Karpatium bis Unter-Badenium)", -17200000, -15032000, "Y-17200000/Y-15032000", "table"),
    ("Phanerozoic", None, None, "", "unmapped"),
    ("um 1730/40", 1730, 1740, "1730~/1740~", "rule"),
    ("1927-28", 1927, 1928, "1927/1928", "rule"),
    ("Jänner 1909", 1909, 1909, "1909-01", "rule"),
    ("1. Juni 1995", 1995, 1995, "1995-06-01", "rule"),
    ("1927-01-xx", 1927, 1927, "1927-01", "rule"),
    ("23.09.1980, 24.09.1980; 02.\u201326.09.1980", 1980, 1980, "1980-09-02/1980-09-26", "rule"),
    ("1920-1960 ca..", 1920, 1960, "1920~/1960~", "rule"),
    ("1996-06-08/09", 1996, 1996, "1996-06-08/1996-06-09", "rule"),
    ("[1915/18]", 1915, 1918, "1915/1918", "rule"),
    ("1660/70", 1660, 1670, "1660/1670", "rule"),
    ("18##-02", 1800, 1899, "1800/1899", "rule"),
    ("19??", 1900, 1999, "1900/1999", "rule"),
    ("09.09.01", 1901, 1901, "1901-09-09", "rule"),
    ("Poststempel: Anger, 6.2.69", 1969, 1969, "1969-02-06", "rule_embedded"),
    ("African | Afrikanisch", None, None, "", "no_date"),
    ("-195000000", -195000000, -195000000, "Y-195000000", "table"),
    ("Roman Imperial | Römische Kaiserzeit", -27, 476, "-0026/0476", "table"),
    ("Spätklassizismus", 1810, 1850, "1810/1850", "table"),
    ('"vor 1914"', None, 1914, "../1914", "rule"),
    ("nicht datiert", None, None, "", "no_date"),
    ("ohne Datierung", None, None, "", "no_date"),
    ("Unbekannt", None, None, "", "no_date"),
    ("ca. 70 v. Chr.-25", None, None, "", "unmapped"),
    ("Nicht-Epoche ohne Zahl", None, None, "", "unmapped"),
]


class ParseTimeTest(unittest.TestCase):
    def test_cases(self):
        for text, begin, end, iso, method in CASES:
            with self.subTest(text=text):
                result = parse_time(text)
                self.assertEqual(
                    (result.begin_year, result.end_year, result.iso, result.method),
                    (begin, end, iso, method),
                )

    def test_timespan_uses_begin_and_end(self):
        result = parse_time("1. Hälfte 20. Jh.", "1900", "1950")
        self.assertEqual((result.begin_year, result.end_year, result.iso, result.method), (1900, 1950, "1900/1950", "timespan"))

    def test_empty_values_have_no_date(self):
        self.assertEqual(parse_time(None).method, "no_date")
        self.assertEqual(parse_time("   ").method, "no_date")


if __name__ == "__main__":
    unittest.main()
