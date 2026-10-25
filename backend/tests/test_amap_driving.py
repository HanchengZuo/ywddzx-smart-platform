import unittest
from unittest.mock import patch
from amap_driving import DrivingUnavailable, fetch_distance, parse_results
from driving_matrix import DatabaseMatrix
from schedule_driving_routes import driving_groups, driving_request, shortest_order


def station(sid, region='甲', longitude=None):
    return dict(station_id=sid, region=region, covered=False, longitude=longitude or 121.1+sid*.01, latitude=31.2)


def request(stations=None, count=1, quota=2, required=(), coverage=None):
    return driving_request(stations or [station(1),station(2),station(3)], count, quota,
                           coverage or [], required, [quota]*count)


class RouteTests(unittest.TestCase):
    def test_shorter_time_wins_even_when_driving_distance_is_longer_and_stations_are_further_apart(self):
        stations=[station(1),station(2,longitude=121.11001),station(3)]
        matrix=DatabaseMatrix({}, {(1,2):dict(seconds=1800,meters=1000),
                                  (1,3):dict(seconds=300,meters=13000),
                                  (2,3):dict(seconds=2500,meters=16000)})
        result=driving_groups(request(stations),matrix)
        self.assertEqual(set(result[0]['station_ids']), {1,3})
        self.assertEqual((result[0]['seconds'],result[0]['meters']), (300,13000))

    def test_single_sample_is_shared_in_both_directions(self):
        matrix=DatabaseMatrix({}, {(1,2):dict(seconds=60,meters=1500)})
        self.assertEqual(matrix.edge(1,2),matrix.edge(2,1))
        matrix.incoming(1,[2]); matrix.incoming(2,[1])
        with self.assertRaises(DrivingUnavailable): matrix.incoming(3,[1])
        self.assertEqual(matrix.edge(1,1),dict(seconds=0,meters=0))

    def test_metering_and_coverage_constraints_are_preserved_before_road_time(self):
        stations=[station(1),station(2),station(3,'乙'),station(4,'乙')]
        matrix=DatabaseMatrix({}, {(a,b):dict(seconds=60 if b<3 else 1800,meters=2000)
                                  for a in range(1,5) for b in range(a+1,5)})
        result=driving_groups(request(stations,required=(3,),coverage=[dict(region='甲',total=2,checked=2,reserved=0),
            dict(region='乙',total=2,checked=0,reserved=0)]),matrix)
        self.assertEqual(set(result[0]['station_ids']),{3,4})

    def test_155_candidate_capacity_determinism_and_local_offline_performance(self):
        matrix=DatabaseMatrix({}, {(a,b):dict(seconds=(b-a)*20,meters=(b-a)*100)
                                  for a in range(1,156) for b in range(a+1,156)})
        data=request([station(i,str(i%7)) for i in range(1,156)],count=7,quota=10)
        result=driving_groups(data,matrix)
        self.assertEqual([len(trip['station_ids']) for trip in result],[10]*7)
        self.assertEqual(len({sid for trip in result for sid in trip['station_ids']}),70)
        self.assertEqual(result,driving_groups(data,matrix))


class TransportTests(unittest.TestCase):
    def test_collector_uses_type_one_and_never_leaks_key_bearing_urls(self):
        with patch('amap_driving.urlopen') as url:
            response=url.return_value.__enter__.return_value
            response.status=200; response.read.return_value=b'{"status":"1","results":[]}'
            fetch_distance('private-test-key',['121.1,31.2'],'121.2,31.2',6)
            self.assertIn('type=1',url.call_args.args[0]); self.assertNotIn('type=0',url.call_args.args[0])
            url.side_effect=RuntimeError('https://secret?key=private-test-key')
            with self.assertRaises(DrivingUnavailable) as caught: fetch_distance('private-test-key',[],'',6)
            self.assertNotIn('private-test-key',str(caught.exception))
        for code in ('10009','10003','99999'):
            with self.assertRaises(DrivingUnavailable) as caught:
                parse_results(dict(status='0',infocode=code,info='private-test-key'),1)
            self.assertNotIn('private-test-key',str(caught.exception))

    def test_invalid_or_unreachable_results_are_not_zero_minutes(self):
        normal=dict(origin_id='1',dest_id='1',duration='20',distance='200')
        for change in (dict(duration='NaN'),dict(distance='-1'),dict(origin_id='2'),dict(dest_id='2'),dict(code='9')):
            with self.assertRaises(DrivingUnavailable): parse_results(dict(status='1',results=[dict(normal,**change)]),1)
        with self.assertRaises(DrivingUnavailable): parse_results(dict(status='1',results=[normal,normal]),2)
        self.assertEqual(parse_results(dict(status='1',results=[dict(origin_id='1',dest_id='1',code='1')]),1),{0:None})
