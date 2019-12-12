from yaml import load, dump
import single_edit_generator as edit_generator
import eval_neutrality_generic as eval_neutrality
import online_algorithm as online_algorithm
import os
import sys


def main(argv):
    with open(str(argv[0])) as yml:
        config = load(yml)

    # generate single mutations if they don't already exist
    if not os.path.exists(config['output_directory'] + '/single_edits'):
        print("found no single edit file, generating")
        single_edits = edit_generator.gen_single_mutations(bugzoo_id=config['bugzoo_id'],
                                                           output_directory=config['output_directory'])
    else:
        print("found single edit file, loading")
        with open(config['output_directory'] + '/single_edits', 'r') as in_file:
            single_edits = in_file.readlines()
            for i in range(len(single_edits)):
                single_edits[i] = single_edits[i].strip('\n')

    # add the number that we have generated to the yaml file; used by neutrality evaluator
    config['single_edit_cardinality'] = len(single_edits)
    with open(str(argv[0]), "w") as yml:
        dump(config, yml, default_flow_style=False)

    # test them for neutrality
    # FIXME: refactor this to happen on demand instead of as a pre-processing step
    if not os.path.exists(config['output_directory'] + '/neutral_mutations'):
        print("found no neutral mutation file, generating mutants")
        # generate neutral mutations, parse output to a file which is saved for check-pointing
        neut = eval_neutrality.EvalNeutrality(edit_list=single_edits, config_path=str(argv[0]))
        neut.run_tests(parallel_workers=config['parallel_workers'])
        neutral_edits = neut.parse_directories()
    else:
        # load from check-pointed file
        print("found neutral mutation file, loading")
        with open(config['output_directory'] + '/neutral_mutations', 'r') as in_file:
            neutral_edits = in_file.readlines()
            for i in range(len(neutral_edits)):
                neutral_edits[i] = neutral_edits[i].strip('\n')

    # online algorithm to make probes
    print("starting online algorithm")
    alg = online_algorithm.OnlineAlgorithm(config_path=str(argv[0]))
    alg.run_tests(parallel_workers=int(config['parallel_workers']), neutral_edit_list=neutral_edits)


if __name__ == "__main__":
    main(sys.argv[1:])
