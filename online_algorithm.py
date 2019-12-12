import bugzoo
from subprocess import call, DEVNULL
import multiprocessing
import numpy as np
from yaml import load
import os


def mwua_sample(weights, choices):
    """
    :param weights: a vector of weights
    :param choices: a vector of choices (e.g. # of mutations to make)
    :return: a selection from the choices according to the weights
    """
    # the following three lines transform the neutrality estimate to an estimate of the density of repairs
    # assuming a linear likelihood
    temp_weights = [_ * i for i, _ in enumerate(weights)]
    total = sum(temp_weights)
    temp_weights = [_ / total for _ in temp_weights]

    return np.random.choice(choices, p=temp_weights)


# TODO: set eta to optimal value somewhere in the code
def mwua_update(weights, choice_to_update, reward=1.0, eta=0.05):
    """
    :param weights: the input weight vector for MWUA
    :param choice_to_update: the index to update
    :param reward: the reward to update at the index
    :param eta: the learning parameter
    :return: the updated vector of weights (normalized)
    """
    weights[choice_to_update] *= (1+reward*eta)
    total = sum(weights)
    for i in range(len(weights)):
        weights[i] /= total
    return weights


class OnlineAlgorithm:

    def __init__(self, config_path):
        with open(config_path) as yml:
            self.config = load(yml)
        # ensure that the bug is built before launching threads
        b = bugzoo.BugZoo()
        bug = b.bugs[self.config['bugzoo_id']]
        b.bugs.build(bug=bug)

    def thread(self, index, return_dict, edits_to_make, num_edits, neg_tests, exp_number):
        output_folder = self.config['output_directory'] + self.config['program'] + '/' + str(exp_number) + '/'

        # create bugzoo instance
        b = bugzoo.BugZoo()

        bug = b.bugs[self.config['bugzoo_id']]
        genprog = b.tools['genprog']
        container = b.containers.provision(bug=bug, tools=[genprog])

        # copy in coverage paths to skip sanity and coverage check time
        call("docker cp " + self.config['output_directory'] + "coverage.path.pos " + container.uid +
             ":/experiment/coverage.path.pos", shell=True)
        call("docker cp " + self.config['output_directory'] + "coverage.path.neg " + container.uid +
             ":/experiment/coverage.path.neg", shell=True)

        invoke_genprog = 'cd /experiment && /opt/genprog/bin/genprog configuration-default --oracle-genome ' + \
                         "\'\"\'" + edits_to_make + "\'\"\'" + ' --search pd-oracle --skip-failed-sanity-tests ' \
                         '--allow-coverage-fail'

        tuple_returned = b.containers.command(container=container, cmd=invoke_genprog)

        call("mkdir -p " + output_folder, shell=True)
        with open(output_folder + str(index), 'w') as out_file:
            out_file.write(tuple_returned.output)

        # TODO: fix this logic; skipping for now
        # Force cleanup of container before thread exits
        call("docker stop " + str(container.uid), shell=True)

        # parse for neutrality
        text = str(tuple_returned.output)
        was_neutral = False
        was_repair = False

        if text.find("was neutral") != -1:
            was_neutral = True
        if text.find("passed " + str(neg_tests)) != -1:
            was_repair = True

        return_dict[index] = {"index": index, "edits_to_make": edits_to_make, "num_edits": num_edits,
                              "neutral": was_neutral, "repair": was_repair}

    def run_tests(self, parallel_workers, neutral_edit_list):
        """
        This handles running a bugzoo-powered evaluation of all of the edits in a list.
        :param parallel_workers: number of processes to try in parallel
        :param neutral_edit_list: the list of neutral edits to compose
        :return:
        """

        experiment = 0
        experiment_limit = 100

        neg_tests = self.config['neg_tests']

        while experiment < experiment_limit:
            if not os.path.exists(self.config['output_directory'] + self.config['program'] + '/' + str(experiment)):

                generation = 0
                generation_limit = self.config['generations']
                space_to_search = self.config['max_mutations']
                weights = [1.0 / space_to_search for _ in range(space_to_search)]
                choices = [_ for _ in range(space_to_search)]

                manager = multiprocessing.Manager()
                return_dict = manager.dict()

                repair_found = False
                while generation < generation_limit:
                    jobs = []
                    for i in range(generation * parallel_workers, (generation + 1) * parallel_workers):
                        # add 1 so that mut. 0 not possible
                        num_edits = mwua_sample(weights=weights, choices=choices) + 1
                        edits_to_make = np.random.choice(neutral_edit_list, num_edits)
                        for j in range(len(edits_to_make)):
                            edits_to_make[j] = edits_to_make[j].strip('\n')
                        edits_to_make = ", ".join(edits_to_make)
                        p = multiprocessing.Process(target=self.thread, args=(i, return_dict, edits_to_make, num_edits,
                                                                              neg_tests, experiment))
                        jobs.append(p)
                        p.start()

                    for process in jobs:
                        process.join()

                    temp_neutrality = []
                    # update the estimate
                    weights = [1.0 / space_to_search for _ in range(space_to_search)]
                    for index, key in enumerate(return_dict.keys()):
                        if return_dict[key]["repair"]:
                            with open(self.config['output_directory'] + self.config['program'] + '/' + str(experiment) +
                                      '/repair', 'w') as out_file:
                                out_file.write(str(index))
                            print("Repair found at index " + str(index))
                            repair_found = True
                        temp_neutrality.append((int(return_dict[key]["num_edits"]), int(return_dict[key]["neutral"])))
                        weights = mwua_update(weights=weights, choice_to_update=int(return_dict[key]["num_edits"]) - 1,
                                              reward=int(return_dict[key]["neutral"]), eta=float(self.config["error"])/2.0)

                    call('docker container prune -f; docker volume prune -f; docker network prune -f', shell=True, stdout=DEVNULL,
                         stderr=DEVNULL)

                    if repair_found:
                        break

                    print("in order applied: ", temp_neutrality)

                    generation += 1

                with open(self.config['output_directory'] + self.config['program'] + '/' + str(experiment) + '/dict', 'w') \
                        as out_file:
                    out_file.write(str(return_dict))

            experiment += 1
