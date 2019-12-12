# This script takes as input a program and uses GenProg to generate a search space of mutations
from subprocess import call
import exhaustive_exploration as exhaustive
import bugzoo


def gen_single_mutations(bugzoo_id, output_directory):
    """
    :return: a list of single edits
    """

    # bugzoo setup
    b = bugzoo.BugZoo()

    print("Instantiating bug reference")
    bug = b.bugs[bugzoo_id]
    b.bugs.build(bug=bug)

    print("Running GenProg to generate coverage paths")
    genprog = b.tools['genprog']
    container = b.containers.provision(bug=bug, tools=[genprog])

    outcome = b.containers.command(container=container,
                                   cmd="genprog configuration-default --search ga --generations 1 --popsize 1"
                                       " --seed 0 --skip-failed-sanity-tests --allow-coverage-fail"
                                       " && cat coverage.path.pos && cat coverage.path.neg")

    call("mkdir -p " + output_directory, shell=True)
    call("docker cp " + container.uid + ":/experiment/coverage.path.pos " + output_directory + "coverage.path.pos", shell=True)
    call("docker cp " + container.uid + ":/experiment/coverage.path.neg " + output_directory + "coverage.path.neg", shell=True)
    call("docker cp " + container.uid + ":/experiment/repair.debug.0 " + output_directory + "repair.debug.0", shell=True)

    print("Generating search space from single edits")
    coverage_paths = [output_directory + 'coverage.path.pos', output_directory + 'coverage.path.neg']
    indices = exhaustive.parse_lists(coverage_paths)
    max_index = exhaustive.get_max_index(program_path=output_directory)
    single_edits = exhaustive.generate_single_edits(covered_indices=indices, max_index=max_index)
    exhaustive.write_edits_to_file(list_to_write=single_edits, folder_path=output_directory,
                                   filename="single_edits")

    call("docker stop " + str(container.uid), shell=True)

    return single_edits
