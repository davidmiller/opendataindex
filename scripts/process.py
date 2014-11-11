import os
import sys
import logging
import urllib
import shutil
import csv
import operator
import itertools
import unittest
from collections import OrderedDict
from pprint import pprint


def get_config():
    base_path = os.path.join(os.getcwd())
    sys.path.append(base_path)
    import config_default
    config = config_default.ODI['cli']
    sys.path.remove(base_path)
    return config


config = get_config()

# https://docs.google.com/a/okfn.org/spreadsheet/ccc?key=0AqR8dXc6Ji4JdGNBWWJDaTlnMU1wN1BQZlgxNHBxd0E&usp=drive_web#gid=0
survey_submissions = config['database']['submissions']
survey_entries = config['database']['entries']

# https://docs.google.com/a/okfn.org/spreadsheet/ccc?key=0AqR8dXc6Ji4JdFI0QkpGUEZyS0wxYWtLdG1nTk9zU3c&usp=drive_web#gid=0
survey_questions = config['database']['questions']

# https://docs.google.com/a/okfn.org/spreadsheet/ccc?key=0Aon3JiuouxLUdEVHQ0c4RGlRWm9Gak54NGV0UlpfOGc&usp=drive_web#gid=0
survey_datasets = config['database']['datasets']

# https://docs.google.com/a/okfn.org/spreadsheet/ccc?key=0AqR8dXc6Ji4JdE1QUS1qNjhvRDJaQy1TbTdJZDMtNFE&usp=drive_web#gid=1
survey_places = config['database']['places']


class AttrDict(dict):
    __getattr__ = dict.__getitem__
    __setattr__ = dict.__setitem__


class Processor(object):
    def download(self):
        '''Download source data from the survey to tmp directory.'''
        if not os.path.exists(config['tmp_path']):
            os.makedirs(config['tmp_path'])
        urllib.urlretrieve(survey_submissions, '{0}/submissions.csv'.format(config['tmp_path']))
        urllib.urlretrieve(survey_entries, '{0}/entries.csv'.format(config['tmp_path']))
        urllib.urlretrieve(survey_questions, '{0}/questions.csv'.format(config['tmp_path']))
        urllib.urlretrieve(survey_datasets, '{0}/datasets.csv'.format(config['tmp_path']))
        urllib.urlretrieve(survey_places, '{0}/places.csv'.format(config['tmp_path']))

    def extract(self):
        '''Extract data from raw Survey files, process and save to data dir'''
        ext = Extractor()
        ext.run()

    def cleanup(self):
        if os.path.exists('tmp'):
            shutil.rmtree('tmp')

    def run(self):
        '''Run all stages of the processing pipeline'''
        self.download()
        self.extract()
        # keep tmp around so we can run extract without download
        # self.cleanup()

    def test(self):
        '''Run tests against extracted data to check all is good.'''
        suite = unittest.TestLoader().loadTestsFromTestCase(TestIndexData)
        unittest.TextTestRunner(verbosity=2).run(suite)


class Extractor(object):
    def __init__(self):
        self.places = self._load_csv('tmp/places.csv')
        self.entries = self._load_csv('tmp/entries.csv')
        self.datasets = self._load_csv('tmp/datasets.csv')
        self.questions = self._load_csv('tmp/questions.csv')
        self.submissions = self._load_csv('tmp/submissions.csv')

        self.current_year = '2014'
        self.years = ['2014', '2013']

        # this will be entry dicts keyed by a tuple of (place_id, dataset_id)
        self.keyed_entries = OrderedDict()

        # after the processing and copying, this has every entry to be written
        self.writable_entries = OrderedDict()

        # stub out the keyed entries
        for p in self.places['dicts']:
            for d in self.datasets['dicts']:
                for year in self.years:
                    self.keyed_entries[(p['id'], d['id'], year)] = AttrDict({
                            'place': p['id'],
                            'dataset': d['id'],
                            'year': year,
                            'timestamp': '',
                            'score': None,
                            'rank': None
                    })

    def run(self):
        # `self.run_entries()` must *always* run first!
        self.run_entries()
        self.run_datasets()
        self.run_questions()
        self.run_places()
        self.run_summary()

    def run_entries(self):

        # walk through the existing entries;
        # copy *forward* any missing place,dataset,year entries
        # eg:
        #   gb,timetables,2013 (have entry)
        #   gb,timetables,2014 (no entry: so copy the 2013 entry forward to 2014)
        for ent in self.entries.dicts:
            self._tidy_entry(ent)
            key = (ent['place'], ent['dataset'], ent['year'])
            self.keyed_entries[key] = ent

        entries_to_write = {}
        populated_entries = {k: v for k, v in self.keyed_entries.items() if
                             v['timestamp'] != ''}
        entries_to_write.update(populated_entries)
        empty_entries = {k: v for k, v in self.keyed_entries.items() if
                         v['timestamp'] == ''}

        # if we have empty entries (should do),
        # then we need to do the copy forward
        if empty_entries:
            for k, v in empty_entries.items():
                related_entries = {x: y for x, y in
                                   populated_entries.iteritems() if
                                   v['place'] == y.place and
                                   v['dataset'] == y.dataset}

                if not related_entries:
                    pass
                else:

                    candidates = [int(key[2]) for key in
                                  related_entries.keys() if
                                  int(key[2]) < int(k[2])]
                    if candidates:
                        # if candidates is empty, then it means we only
                        # had related entries forward in time, so we *don't*
                        # have any copy forward to do
                        year_to_copy = max(candidates)
                        entry_to_copy = AttrDict(related_entries[(k[0], k[1], str(year_to_copy))].copy())
                        entry_to_copy['year'] = k[2]
                        entries_to_write.update({
                            k: entry_to_copy
                        })

        self.writable_entries = AttrDict(self._rank_entries(OrderedDict(entries_to_write)))

        ## write the entries.csv

        # play around with column ordering in entries.csv
        # drop off censusid (first col) and timestamp
        fieldnames = self.entries.columns[1:]
        # move year around
        fieldnames[0:3] = ['place', 'dataset', 'year']
        fieldnames.insert(3, 'score')
        fieldnames.insert(4, 'rank')
        fieldnames.insert(5, 'isopen')
        # move timestamp to the end
        fieldnames.insert(-1, 'timestamp')

        writer = csv.DictWriter(open('data/entries.csv', 'w'),
                fieldnames=fieldnames,
                lineterminator='\n'
                )
        writer.writeheader()
        writer.writerows([x[1] for x in self.writable_entries.iteritems()])

    def run_datasets(self):
        fieldnames = self.datasets.columns
        fieldnames += ['score', 'rank']
        extra_years = [y for y in self.years if y != self.current_year]
        for year in extra_years:
            fieldnames += ['score_{0}'.format(year), 'rank_{0}'.format(year)]

        ## set scores
        for dataset in self.datasets.dicts:
            for year in self.years:
                score_lookup = 'score'
                if not year == self.current_year:
                    score_lookup = 'score_{0}'.format(year)

                to_score = [x[1].score for x in
                            self.writable_entries.iteritems() if
                            x[1].dataset == dataset.id and x[1].year == year and
                            x[1].score is not None]

                # place count * 100 score per place
                place_count = len(set([x[0][0] for x in
                            self.writable_entries.iteritems() if
                            x[1].dataset == dataset.id and
                            x[1].year == year and
                            x[1].score is not None]))

                total_possible_score = place_count * 100.0

                if not to_score:
                    score = None
                else:
                    score = int(round(100 * sum(to_score) /
                                total_possible_score, 0))

                dataset[score_lookup] = score

        # build lookups for rank, now that we have scores
        lookup = {}
        for year in self.years:
            score_lookup = 'score'
            rank_lookup = 'rank'
            if not year == self.current_year:
                score_lookup = 'score_{0}'.format(year)
                rank_lookup = 'rank_{0}'.format(year)
            year_scores = sorted(list(set([d[score_lookup] for d in
                                 self.datasets.dicts])))
            year_scores.reverse()
            year_lookup = {}
            for index, score in enumerate(year_scores):
                if score is None:
                    pass
                else:
                    year_lookup.update({str(score): index + 1})

            lookup.update({year: year_lookup})

        # set ranks
        for dataset in self.datasets.dicts:
            for year in self.years:
                score_lookup = 'score'
                rank_lookup = 'rank'
                if not year == self.current_year:
                    score_lookup = 'score_{0}'.format(year)
                    rank_lookup = 'rank_{0}'.format(year)

                if dataset[score_lookup] is None:
                    dataset[rank_lookup] = None
                else:
                    dataset[rank_lookup] = lookup[year][str(dataset[score_lookup])]

        self._write_csv(self.datasets.dicts, 'data/datasets.csv', fieldnames)

    def run_questions(self):
        # get rid of translations (column 8 onwards) for the time being as not
        # checked and not being used
        icon_translate = {
            'file-alt': 'file-o',
            'eye-open': 'eye',
            'keyboard': 'keyboard-o',
            'time': 'clock-o'
        }
        transposed = list(zip(*list(self.questions.rows)))
        newrows = list(zip(*(transposed[:8])))
        for index, q in enumerate(newrows):
            if q[6] and q[6] in icon_translate:
                # import ipdb;ipdb.set_trace()
                q = list(q)
                q[6] = icon_translate[q[6]]
                q = tuple(q)
                newrows[index] = q

        self._write_csv(newrows, 'data/questions.csv')

    def run_places(self):
        fieldnames = self.places.columns
        fieldnames += ['score', 'rank']
        extra_years = [y for y in self.years if y != self.current_year]
        for year in extra_years:
            fieldnames += ['score_{0}'.format(year), 'rank_{0}'.format(year)]
        fieldnames += ['submitters', 'reviewers']

        ## set scores
        for place in self.places.dicts:
            for year in self.years:
                score_lookup = 'score'
                if not year == self.current_year:
                    score_lookup = 'score_{0}'.format(year)

                to_score = [x[1].score for x in
                            self.writable_entries.iteritems() if
                            x[1].place == place.id and x[1].year == year and
                            x[1].score is not None]

                # 10 datasets * 100 score per dataset
                total_possible_score = 10 * 100.0

                if not to_score:
                    score = None
                else:
                    score = int(round(100 * sum(to_score) /
                                total_possible_score, 0))

                place[score_lookup] = score

        # build lookups for rank, now that we have scores
        lookup = {}
        for year in self.years:
            score_lookup = 'score'
            rank_lookup = 'rank'
            if not year == self.current_year:
                score_lookup = 'score_{0}'.format(year)
                rank_lookup = 'rank_{0}'.format(year)
            year_scores = sorted(list(set([p[score_lookup] for p in
                                 self.places.dicts])))
            year_scores.reverse()
            year_lookup = {}
            for index, score in enumerate(year_scores):
                if score is None:
                    pass
                else:
                    year_lookup.update({str(score): index + 1})

            lookup.update({year: year_lookup})

        # set ranks
        for place in self.places.dicts:
            for year in self.years:
                score_lookup = 'score'
                rank_lookup = 'rank'
                if not year == self.current_year:
                    score_lookup = 'score_{0}'.format(year)
                    rank_lookup = 'rank_{0}'.format(year)

                if place[score_lookup] is None:
                    place[rank_lookup] = None
                else:
                    place[rank_lookup] = lookup[year][str(place[score_lookup])]

        # set reviewers and submitters
        submitreviewlookup = {}
        for submission in self.submissions.dicts:
            if submitreviewlookup.get('place'):
                submitreviewlookup['place']['submitters'] += u'{0}{1}'.format(
                    ';', submission['submitter'])
                submitreviewlookup['place']['reviewers'] += u'{0}{1}'.format(
                    ';', submission['reviewer'])
            else:
                submitreviewlookup.update({
                    submission['place']: {
                        'reviewers': submission['reviewer'],
                        'submitters': submission['submitter']
                    }
                })

        for place in self.places.dicts:
            if place['id'] in submitreviewlookup:
                place['submitters'] = submitreviewlookup[place['id']]['submitters']
                place['reviewers'] = submitreviewlookup[place['id']]['reviewers']

        self._write_csv(self.places.dicts, 'data/places.csv', fieldnames)

    def run_summary(self):
        fieldnames = ['id', 'title', 'value']
        extra_years = [y for y in self.years if y != self.current_year]
        for year in extra_years:
            fieldnames += ['value_{0}'.format(year)]

        rows = [
            ['places_count', 'Number of Places'],
            ['entries_count', 'Number of Entries'],
            ['open_count', 'Number of Open Datasets'],
            ['open_percent', 'Percent Open']
        ]

        for year in self.years:
            value_lookup = 'value'
            if not year == self.current_year:
                value_lookup = 'value_{0}'.format(year)
            year_numentries = len([x for x in self.writable_entries if
                                   x[2] == year])
            year_numplaces = len(set([x[0] for x in
                                      self.writable_entries if
                                      x[2] == year]))
            year_numopen = len([x for x in self.entries.dicts if x.isopen])
            year_percentopen = int(round((100.0 * year_numopen) /
                                          year_numentries, 0))
            rows[0].append(year_numplaces)
            rows[1].append(year_numentries)
            rows[2].append(year_numopen)
            rows[3].append(year_percentopen)

        self._write_csv([fieldnames] + rows, 'data/summary.csv')

    def _tidy_entry(self, entry_dict):
        # TODO: tidy up timestamp
        del entry_dict['censusid']

        # standardize y/n values (should go into DB at some point!)
        correcter = {
            'yes': 'Y',
            'yes ': 'Y',
            'no': 'N',
            'no ': 'N',
            'unsure': '?'
        }
        for qu in self.questions.dicts:
            # y/n questions have a weight
            if qu.score and int(qu.score) > 0:
                entry_dict[qu.id] = correcter[entry_dict[qu.id].lower()]

        entry_dict['rank'] = ''
        entry_dict['score'] = self._score(entry_dict)
        # Data is exists, is open, and publicly available, machine readable etc
        entry_dict['isopen'] = bool(
            entry_dict.exists == 'Y' and
            entry_dict.openlicense == 'Y' and
            entry_dict.public == 'Y' and
            entry_dict.bulk == 'Y' and
            entry_dict.machinereadable == 'Y'
          )

    def _score(self, entry):
        def summer(memo, qu):
            if qu.score and entry[qu.id] == 'Y':
                memo = memo + int(qu.score)
            return memo;
        return reduce(summer, self.questions.dicts, 0)

    def _rank_entries(self, entries):

        def _datasetscoresort(obj):
            return obj[1]['dataset'], -obj[1]['score']

        def _scoresort(obj):
            return obj[1]['score']

        rv = OrderedDict()
        workspace = []

        for year in self.years:
            year_entries = OrderedDict(
                sorted([e for e in entries.iteritems() if
                        e[0][2] == year], key=_datasetscoresort)
            )

            for dataset in [d[0] for d in self.datasets['rows'][1:]]:
                workspace.append(
                    OrderedDict(sorted([(k, v) for k, v in
                                year_entries.iteritems() if k[1] == dataset],
                                key=_scoresort, reverse=True)
                ))

        for o in workspace:
            lookup = {}
            scores = sorted(list(set([v['score'] for k, v in o.iteritems()])))
            scores.reverse()
            for index, score in enumerate(scores):
                lookup.update({str(score): index + 1})
            for e in o.iteritems():
                e[1]['rank'] = lookup[str(e[1]['score'])]
            rv.update(OrderedDict(o))

        return rv

    @classmethod
    def _load_csv(self, path):
        reader = csv.reader(open(path))
        columns = reader.next()
        # lowercase the columnss
        columns = [ x.lower() for x in columns ]
        rows = [ row for row in reader ]
        dictized = [ AttrDict(dict(zip(columns, row))) for row in rows ]
        return AttrDict({
            'columns': columns,
            'rows': [columns] + rows,
            'dicts': dictized
            })

    def _write_csv(self, rows, path, fieldnames=None):
        if fieldnames:
            writer = csv.DictWriter(open(path, 'w'), fieldnames=fieldnames, lineterminator='\n')
            writer.writeheader()
        else:
            writer = csv.writer(open(path, 'w'), lineterminator='\n')
        writer.writerows(rows)


class TestIndexData(unittest.TestCase):
    def setUp(self):
        self.entries = Extractor._load_csv('data/entries.csv')
        self.places = Extractor._load_csv('data/places.csv')
        self.keyed = dict([ [(e.place, e.dataset), e] for e in
            self.entries.dicts ])

    def test_entries_score(self):
        au_timetables = self.keyed[('au', 'timetables')]
        au_elections = self.keyed[('au', 'elections')]
        self.assertEqual(au_timetables.score, '45')
        self.assertEqual(au_elections.score, '100')

    def test_entries_rank(self):
        out = self.keyed[('ca', 'budget')]
        self.assertEqual(out.rank, '1')

    def test_entries_isopen(self):
        out = self.keyed[('gb', 'spending')]
        self.assertEqual(out.isopen, 'True')

    def test_place_scores(self):
        out = dict([[x.id, x] for x in self.places.dicts])
        self.assertEqual(out['gb'].score, '94')
        self.assertEqual(out['au'].score, '66')

    def test_place_rank(self):
        out = dict([[x.id, x] for x in self.places.dicts])
        self.assertEqual(out['gb'].rank, '1')
        self.assertEqual(out['au'].rank, '10')

    def test_summary(self):
        summary_all = Extractor._load_csv('data/summary.csv')
        summary = AttrDict([[x.id, x] for x in summary_all.dicts])

        self.assertEqual(summary.places_count.value, '249')
        self.assertEqual(summary.open_count.value, '86')
        self.assertEqual(summary.open_percent.value, '11')

import sys
import optparse
import inspect

def _object_methods(obj):
    methods = inspect.getmembers(obj, inspect.ismethod)
    methods = filter(lambda (name,y): not name.startswith('_'), methods)
    methods = dict(methods)
    return methods

if __name__ == '__main__':
    _methods = _object_methods(Processor)

    usage = '''%prog {action}

Actions:
    '''
    usage += '\n    '.join(
        [ '%s: %s' % (name, m.__doc__.split('\n')[0] if m.__doc__ else '') for (name,m)
        in sorted(_methods.items()) ])
    parser = optparse.OptionParser(usage)
    # Optional: for a config file
    # parser.add_option('-c', '--config', dest='config',
    #         help='Config file to use.')
    options, args = parser.parse_args()

    if not args or not args[0] in _methods:
        parser.print_help()
        sys.exit(1)

    method = args[0]
    getattr(Processor(), method)(*args[1:])
