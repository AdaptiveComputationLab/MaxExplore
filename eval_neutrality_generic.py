import bugzoo
from multiprocessing import Pool
from subprocess import call
from yaml import load
import datetime
import os


class EvalNeutrality:
    def __init__(self, edit_list, config_path):
        self.edit_list = edit_list
        self.config_path = config_path
        with open(config_path) as yml:
            self.config = load(yml)

    def parse_directories(self):
        call("cd " + self.config['output_directory'] + '/neutral_check_directory && grep -rn "was neutral" >>'
                                                       ' ../neutral_mutations_unparsed', shell=True)
        with open(self.config['output_directory'] + '/neutral_mutations_unparsed', 'r') as in_file:
            lines = in_file.readlines()
            neutral_mutations = []
            for line in lines:
                neutral_mutations.append(line[line.rfind(":") + 1:line.find(" was neutral")])
            with open(self.config['output_directory'] + '/neutral_mutations', 'w') as out_file:
                out_file.writelines('\n'.join(neutral_mutations))
        return neutral_mutations

    def thread(self, index):
        """
        Contains the logic for evaluating the neutrality of a single mutation; thread-safe afaik
        :param index: the index number of the thread being run
        :return:
        """
        end = datetime.datetime.now() + datetime.timedelta(days=float(self.config["days_to_run_neutrality"]))

        config = self.config

        edits_per_thread = int(int(config["single_edit_cardinality"]) / int(config["parallel_workers"]))

        range_min = 0 + (index * edits_per_thread)
        range_max = (edits_per_thread + (index * edits_per_thread)) if index < (int(config["parallel_workers"]) - 1) \
            else int(config["single_edit_cardinality"])

        # bugzoo setup per thread
        b = bugzoo.BugZoo()
        bug = b.bugs[config['bugzoo_id']]
        genprog = b.tools['genprog']

        # iterate through assigned range
        for a in range(range_min, range_max):
            # check that the work has not been done already (check-pointing)
            if not os.path.exists(config["output_directory"] + 'neutral_check_directory/' + str(a) + '/'):
                # check that time limit for neutrality evaluation has not been exceeded
                if not datetime.datetime.now() > end:
                    print(a)

                    container = b.containers.provision(bug=bug, tools=[genprog])

                    # copy in coverage paths to skip sanity and coverage check time
                    call("docker cp " + config['output_directory'] + "coverage.path.pos " + container.uid +
                         ":/experiment/coverage.path.pos", shell=True)
                    call("docker cp " + config['output_directory'] + "coverage.path.neg " + container.uid +
                         ":/experiment/coverage.path.neg", shell=True)

                    # apply edit a
                    edit_string = self.edit_list[a]

                    ret = b.containers.command(container=container,
                                               cmd='rm *.cache; genprog configuration-default --search pd-oracle '
                                                   '--skip-failed-sanity-tests --allow-coverage-fail --oracle-genome ' +
                                                   "\'\"\'" + edit_string.strip('\n') + "\'\"\'")
                    # save to file
                    output_folder = config["output_directory"] + 'neutral_check_directory/' + str(a) + '/'
                    call('mkdir -p ' + output_folder, shell=True)
                    with open(output_folder + "repair.debug.oracle", 'w') as out_file:
                        out_file.write(ret.output)

                    # clean up thread before exiting
                    call("docker stop " + str(container.uid), shell=True)

        print("thread " + str(index) + " is done")

    def run_tests(self, parallel_workers):
        """
        This handles running a bugzoo-powered evaluation of all of the edits in a list.
        :param parallel_workers: number of processes to try in parallel
        :return:
        """
        with Pool(processes=parallel_workers) as pool:
            pool.map(self.thread, range(parallel_workers))
        call("docker container prune -f; docker volume prune -f", shell=True)
