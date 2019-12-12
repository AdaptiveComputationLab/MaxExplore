"""
This code implements utilities for performing an exhaustive exploration of the local space near a program.
It does so by ingesting coverage path files, and parsing them to find all of the referenced AST nodes.
Then it generates all possible mutations according to the typical GenProg assumptions of fault and fix spaces.
"""
from subprocess import call
import random


def get_max_index(program_path):
    """
    This assumes GenProg has generated coverage files
    this tool runs it once before this is invoked to ensure this is the case
    :param program_path:
    :return:
    """
    with open(program_path + 'repair.debug.0') as in_file:
        lines = in_file.read()

        max_index = int(lines[lines.find("[1,") + 3:lines.find("]")])
        print("DEBUG: max_index is " + str(max_index))

        return max_index


def parse_lists(list_of_files):
    """
    This function extracts only the indices in the AST that are contained in covered paths (exercised by the test suite)
    :param list_of_files: absolute paths to all coverage paths to be considered
    :return: a sorted list of all of the AST nodes that are covered by the test suite
    """
    list_of_indices = []
    for file_name in list_of_files:
        with open(file_name) as input_file:
            for ast_node in input_file:
                ast_node = int(ast_node.strip())
                if ast_node not in list_of_indices:
                    list_of_indices.append(ast_node)
    return sorted(list_of_indices)


def generate_single_edits(covered_indices, max_index):
    """
    This function is used to generate new edits from the list of indices it is passed (these may not be neutral)
    :param covered_indices: the list of AST nodes on the covered path
    :param max_index: the list of all AST nodes in the program (source material for appends)
    :return: a list of single edits (GenProg-formatted AST patch strings)
    """

    list_of_edits = []

    for a in covered_indices:
        list_of_edits.append('d(%s)' % a)

        for b in range(1, max_index + 1):
            b = str(b)
            if a != b:
                list_of_edits.append('a(%s,%s)' % (a, b))

    return list_of_edits


def write_edits_to_file(list_to_write, folder_path, filename):
    """
    Writes the edit list to a file, one per line
    :param list_to_write: the list of GenProg-formatted AST patch strings
    :param folder_path: the absolute path of the folder to write the file (will be generated if it does not exist)
    :param filename: the name of the file to be created
    """
    call('mkdir -p ' + folder_path, shell=True)
    random.shuffle(list_to_write)
    with open(folder_path + filename, 'w') as out_file:
        for line in list_to_write:
            out_file.write(line + '\n')
