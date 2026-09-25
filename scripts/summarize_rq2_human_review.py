"""Summarize two completed blind rating sheets; write private results only."""

from pathlib import Path
import argparse
import csv
import json
import statistics

from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('state_score_0_2', 'graph_score_0_2', 'difficulty_score_0_2')


def read_scores(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    result = {}
    for row in rows:
        code = (row['case_code'], row['option_code'])
        if code in result:
            raise ValueError(f'duplicate rating code in {path.name}')
        scores = {}
        for field in FIELDS:
            value = row[field].strip()
            if value and value not in ('0', '1', '2'):
                raise ValueError(f'invalid {field} in {path.name}')
            scores[field] = int(value) if value else None
        result[code] = scores
    return result


def summarize(key, first, second):
    valid = {(item['case_code'], item['option_code']): item for item in key
             if item['status'] == 'VALID'}
    if set(first) != set(valid) or set(second) != set(valid):
        raise ValueError('rating sheets do not match the sealed valid options')
    if not any(first[code][field] is not None and second[code][field] is not None
               for code in valid for field in FIELDS):
        raise ValueError('no independently scored options; collect both rating sheets first')
    cases = {}
    for code, item in valid.items():
        cases.setdefault(item['case_code'], {})[item['policy']] = code
    all_cases = {item['case_code'] for item in key}
    result = {'n_selected_cases': len(all_cases), 'n_valid_options': len(valid),
              'n_invalid_agent_options': sum(item['policy'] == 'Agent' and
                                             item['status'] == 'INVALID' for item in key),
              'criteria': {}}
    for field in FIELDS:
        available = [code for code in valid if first[code][field] is not None and
                     second[code][field] is not None]
        kappa = (float(cohen_kappa_score(
            [first[c][field] for c in available],
            [second[c][field] for c in available], weights='linear', labels=[0, 1, 2]))
            if available else None)
        if kappa is not None and (kappa != kappa):
            kappa = None
        differences = []
        for options in cases.values():
            if set(options) != {'B+', 'Agent'}:
                continue
            bplus, agent = options['B+'], options['Agent']
            if any(r[code][field] is None for r in (first, second)
                   for code in (bplus, agent)):
                continue
            b_score = (first[bplus][field] + second[bplus][field]) / 2
            a_score = (first[agent][field] + second[agent][field]) / 2
            differences.append(a_score - b_score)
        result['criteria'][field] = {
            'n_options_with_two_scores': len(available),
            'n_paired_cases_with_complete_scores': len(differences),
            'mean_agent_minus_bplus': statistics.mean(differences) if differences else None,
            'median_agent_minus_bplus': statistics.median(differences) if differences else None,
            'weighted_cohen_kappa_linear': kappa,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path,
                        default=ROOT / 'data/processed/rq2_human_review')
    args = parser.parse_args()
    directory = args.directory.resolve()
    if not directory.is_relative_to((ROOT / 'data').resolve()):
        raise ValueError('rating files must remain inside ignored data/')
    key = json.loads((directory / 'sealed_key.json').read_text(encoding='utf-8'))
    first = read_scores(directory / 'rater_1.csv')
    second = read_scores(directory / 'rater_2.csv')
    summary = summarize(key, first, second)
    output = directory / 'private_summary.json'
    if output.exists():
        raise FileExistsError('private summary already exists; refusing overwrite')
    output.write_text(json.dumps(summary, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
