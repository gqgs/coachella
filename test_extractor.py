import unittest
from extractor import parse_multi_day_schedule

class TestExtractor(unittest.TestCase):
    def test_multi_day_extraction(self):
        mock_text = """
Welcome to Coachella!

Friday, April 10:
4:00pm - Livestream begins
5:20pm - Teddy Swims
7:00pm - The xx
9:05pm - Sabrina Carpenter
12:00am - Anyma
[Rebroadcast]

Saturday, April 11:
4:00pm - Live music returns
5:30pm - Addison Rae
7:00pm - GIVĒON
9:00pm - The Strokes
11:25pm - Justin Bieber
[Rebroadcast]

Sunday, April 12:
4:00pm - Wet Leg
6:10pm - Major Lazer
7:50pm - Young Thug
9:55pm - KAROL G

Catch the rest of the Coachella livestreams here...
        """
        
        results = parse_multi_day_schedule(mock_text)
        
        # Verify days are present
        self.assertIn("Friday", results)
        self.assertIn("Saturday", results)
        self.assertIn("Sunday", results)
        
        # Check Friday
        friday = results["Friday"]
        self.assertEqual(len(friday), 4) # teddy, xx, sabrina, anyma
        self.assertEqual(friday[0]["artist"], "Teddy Swims")
        self.assertEqual(friday[0]["start"], "17:20")
        self.assertEqual(friday[3]["artist"], "Anyma")
        self.assertEqual(friday[3]["start"], "24:00")
        self.assertEqual(friday[3]["end"], "25:00")
        
        # Check Saturday
        saturday = results["Saturday"]
        self.assertEqual(len(saturday), 4)
        self.assertEqual(saturday[0]["artist"], "Addison Rae")
        self.assertEqual(saturday[3]["artist"], "Justin Bieber")
        self.assertEqual(saturday[3]["start"], "23:25")
        self.assertEqual(saturday[3]["end"], "25:00")
        
        # Check Sunday
        sunday = results["Sunday"]
        self.assertEqual(len(sunday), 4)
        self.assertEqual(sunday[0]["artist"], "Wet Leg")
        self.assertEqual(sunday[3]["artist"], "KAROL G")
        self.assertEqual(sunday[3]["end"], "24:00")

if __name__ == "__main__":
    unittest.main()
