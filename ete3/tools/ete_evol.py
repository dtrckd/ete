# #START_LICENSE###########################################################
#
#
# This file is part of the Environment for Tree Exploration program
# (ETE).  http://etetoolkit.org
#
# ETE is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# ETE is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public
# License for more details.
#
# You should have received a copy of the GNU General Public License
# along with ETE.  If not, see <http://www.gnu.org/licenses/>.
#
#
#                     ABOUT THE ETE PACKAGE
#                     =====================
#
# ETE is distributed under the GPL copyleft license (2008-2015).
#
# If you make use of ETE in published work, please cite:
#
# Jaime Huerta-Cepas, Joaquin Dopazo and Toni Gabaldon.
# ETE: a python Environment for Tree Exploration. Jaime BMC
# Bioinformatics 2010,:24doi:10.1186/1471-2105-11-24
#
# Note that extra references to the specific methods implemented in
# the toolkit may be available in the documentation.
#
# More info at http://etetoolkit.org. Contact: huerta@embl.de
#
#
# #END_LICENSE#############################################################
from __future__ import absolute_import
from __future__ import print_function

from .utils import which, colorify
from ..evol.control import PARAMS, AVAIL, PARAMS_DESCRIPTION
from .. import EvolTree, random_color, add_face_to_node, TextFace, TreeStyle
from ..treeview.layouts import evol_clean_layout
from ..evol import Model
from argparse import RawTextHelpFormatter
from multiprocessing import Pool, Queue
from subprocess import Popen, PIPE
import sys
import os, re
import signal
import time

from warnings import warn

DESC = ("Run/Load evolutionary tests, store results in a given oputput folder\n"
        "********************************************************************")

def init_worker():
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def populate_args(evol_args_p):
    evol_args_p.formatter_class = RawTextHelpFormatter
    evol_args = evol_args_p.add_argument_group('ETE-EVOL OPTIONS')
    evol_args.add_argument("--models", dest="models",
                           nargs="+",
                           help="""choose evolutionary models (Model name) among:
=========== ============================= ==================
Model name  Description                   Model kind
=========== ============================= ==================\n%s
=========== ============================= ==================\n
                           """ % (
                               '\n'.join([' %-8s    %-27s   %-15s' % \
                                          ('%s' % (x), AVAIL[x]['evol'],
                                           AVAIL[x]['typ']) for x in sorted (
                                              sorted (AVAIL.keys()),
                                              key=lambda x: AVAIL[x]['typ'],
                                              reverse=True)])),
                           metavar='[...]')

    evol_args.add_argument("--alg", dest="alg",
                           type=str,
                           help=("Link tree to a multiple sequence alignment"
                                 " (codons)."))

    evol_args.add_argument("--node_ids", dest="node_ids",
                           action='store_true',
                           help=("Prints the correspondence between PAML "
                                 "node IDs and node names (ancestors will be "
                                 "displayed as list of descendants), and exit"))

    evol_args.add_argument("--clear_all", dest="clear_all",
                           action='store_true',
                           help=("Clear any data present in the output directory."))

    evol_args.add_argument("--prev_models", dest="prev_models",
                           type=str, nargs='+',
                           help=("directory where pre-calculated models are "
                                 "stored, followed by coma model-name.\n"
                                 "example: --prev_models /path1/,M2 /path2/,M1\n"
                                 "will load models from path1 under the name "
                                 "'M2', and from path2 into 'M1'"))
    evol_args.add_argument("--view", dest="show", action='store_true',
                           help=("Opens ETE interactive GUI to visualize tree and "
                                 "select model(s) to render."))
    evol_args.add_argument("--noimg", dest="noimg", action='store_true',
                           help=("Do not generate images."))
    evol_args.add_argument("--clean_layout", dest="clean_layout",
                           action='store_true',
                           help=("Other visualization option, with omega values "
                                 "written on branches"))
    evol_args.add_argument("--histface", dest="histface",
                           type=str, nargs='+',
                           choices=['bar', 'stick', 'curve',
                                    '+-bar', '+-stick', '+-curve'],
                           help=("Type of histogram face to be used for site "
                                 "models. If preceded by '+-' error bars are "
                                 "also drawn."))

    # evol_args.add_argument("-o", "--output_dir", dest="outdir",
    #                        type=str, default='/tmp/ete3-tmp/',
    #                        help=("directory where to store computed models."
    #                              "subderectories with model names will be created"))

    codeml_mk = evol_args_p.add_argument_group("CODEML TREE CONFIGURATION OPTIONS")

    codeml_mk.add_argument('--mark', dest="mark", nargs='+',
                           help=(
                               "mark branches of the input tree. PAML node IDs "
                               "or names can be used. \n - Names separated by "
                               "single coma will be marked individually. \n - "
                               "Names separated by double comas will mark the "
                               "tree at the common ancestor. \n - Names "
                               "separated by "
                               "triple comas will mark the tree from the common"
                               "ancestor.\nSpaces will be used between these "
                               "elements for new marks. \n"
                               "Example: '--mark "
                               "Homo,,,Chimp Orang,Gorilla Mouse,,Rat' \n"
                               "Will result in marking with #1 Homo, Chimp and "
                               "their common ancestor; \nwith #2 Orang and "
                               "Gorilla nothing else; \nand with #3 the common "
                               "ancestor of Mouse and Rat, but not the leaves."
                               ))

    codeml_mk.add_argument('--interactive', dest="mark_gui", action="store_true",
                           help=("open the input tree in GUI to allow to "
                                 "interactive marking of branches for CodeML."))

    codeml_mk.add_argument('--leaves', dest="mark_leaves", action="store_true",
                           help=("Mark successively all the leaves of the input "
                                 "tree and run branch models on each of them."))

    codeml_mk.add_argument('--internals', dest="mark_internals",
                           action="store_true",
                           help=("Mark successively all the internal node of "
                                 "the input tree (but the root) and run\n"
                                 "branch models on each of them."))

    codeml_ts = evol_args_p.add_argument_group("CODEML TEST OPTIONS")

    codeml_ts.add_argument('--tests', dest="tests", nargs='+', default='auto',
                           type=str,
                           help=("Defines the set of tests to perform.\n"
                                 " example: --test M1,M2 b_neut,b_free\n"
                                 "Will do a likelihood ratio tests between "
                                 "M1 and M2, and between any b_neut and b_free"
                                 "computed\n(only trees with identical marks "
                                 "will be compared)."))

    codeml_gr = evol_args_p.add_argument_group("CODEML MODEL CONFIGURATION OPTIONS")

    params = "".join('[%4s] %-13s' % (PARAMS[p], p) + ('' if i % 4 else '\n')
                     for i, p in enumerate(sorted(PARAMS, key=lambda x: x.lower()), 1))
    
    codeml_gr.add_argument('--codeml_config_file', dest="config_file", metavar="",
                           default=None,
                           help=("CodeML configuration file to be used instead"
                                 "of default models provided\n"))

    codeml_gr.add_argument('--codeml_param', dest="params", metavar="",
                           nargs='+', default=[],
                           help=("extra parameter to be interpreted by CodeML "
                                 "and modify the default settings of models.\n"
                                 "available keywords are accepted [default "
                                 "values]:\n" + params +
                                 "\nexample: verbose,2 omega,1"))

    codeml_gr.add_argument('--codeml_help', action='store_true', dest='super_help',
                           help=("show detailed description on codeml "
                                 "parameters for model configuration "
                                 "and exit."))

    exec_group = evol_args_p.add_argument_group('EXECUTION MDE OPTIONS')
    exec_group.add_argument("-C", "--cpu", dest="maxcores", type=int,
                            default=1, help="Maximum number of CPU cores"
                            " available in the execution host. If higher"
                            " than 1, tasks with multi-threading"
                            " capabilities will enabled (if 0 all available)"
                            " cores will be used")

    exec_group.add_argument("--codeml_binary", dest="codeml_binary",
                            help="[%(default)s] path to CodeML binary")
    exec_group.add_argument("--slr_binary", dest="slr_binary",
                            help="[%(default)s] path to Slr binary")

def parse_config_file(fpath):
    params = {}
    for line in open(fpath):
        try:
            k, v = [i.strip() for i in line.split('*')[0].split('=')]
        except ValueError:
            continue
        params[k] = v
    return params

def find_binary(binary):
    bin_path = os.path.join(os.path.split(which("ete3"))[0], "ete3_apps", "bin", binary)

    if not os.path.exists(bin_path):
        bin_path = os.path.expanduser("~/.etetoolkit/ext_apps-latest/bin/"+binary)

    if not os.path.exists(bin_path):
        bin_path = which(binary)

    if not os.path.exists(bin_path):
        print(colorify("%s binary not found!" %binary, "lred"))
        bin_path = binary
    print("Using: %s" %bin_path)
    return bin_path

def marking_layout(node):
    '''
    layout for interactively marking CodemlTree
    '''
    color_cycle = random_color(num=10, h=0.5)
    # [u'#E24A33', u'#348ABD', u'#988ED5',
    #                u'#777777', u'#FBC15E', u'#8EBA42',
    #                u'#FFB5B8']
    node.img_style["size"] = 0

    if hasattr(node, "collapsed"):
        if node.collapsed == 1:
            node.img_style["draw_descendants"]= False

    if hasattr(node, 'mark') and node.mark != '':
        mark = int(node.mark.replace('#', ''))
        node_color = color_cycle[(mark - 1)]
        node.img_style["fgcolor"] = node_color
        label_face = TextFace(str(mark).center(3), fsize=12, fgcolor="white",
                              ftype="courier")
        label_face.inner_background.color = node_color
    else:
        node_color = 'slateGrey'
        label_face = TextFace("   ", fsize=12, fgcolor="white", ftype="courier")
        label_face.inner_background.color = node_color

    label_face.inner_border.width = 1
    label_face.margin_top = 2
    label_face.margin_bottom = 2

    add_face_to_node(label_face, node, column=0, position="branch-right")

    if node.is_leaf():
        add_face_to_node(TextFace(" %s" %node.name, ftype="courier",
                                  fgcolor="#666666"), node, column=10,
                         position="branch-right")
    else:
        add_face_to_node(TextFace(" %s" %node.name, fsize=8, ftype="courier",
                                  fgcolor="#666666"), node, column=0,
                         position="branch-top")

def clean_tree(tree):
    """
    remove marks from tree
    """
    for n in tree.get_descendants() + [tree]:
        n.mark = ''

def run_one_model(tree, model_name):
    """
    needed for multiprocessing
    """
    tree.run_model(model_name)

def get_node(tree, node):
    res = tree.search_nodes(name=node)
    if len(res) > 1:
        exit('ERROR: more than 1 node with name: %s' % node)
    elif len(res) < 1:
        res = tree.search_nodes(node_id=int(node))
        if len(res) < 1:
            exit('ERROR: node %s not found' % node)
    return res[0]

def get_marks_from_args(tree, args):
    marks = []
    nodes = []
    # use the GUI
    if args.mark_gui:
        if args.mark_leaves or args.mark_internals or args.mark:
            exit('ERROR: incompatible marking options')
        ts = TreeStyle()
        ts.layout_fn = marking_layout
        ts.show_leaf_name = False
        tree._set_mark_mode(True)
        tree.show(tree_style=ts)
        tree._set_mark_mode(False)
        for n in tree.iter_descendants():
            if n.mark:
                marks.append(n.mark)
                nodes.append(n.node_id)
        if marks:
            marks = [marks]
            nodes = [nodes]
    # use the command line
    if args.mark:
        if args.mark_leaves or args.mark_internals:
            exit('ERROR: incompatible marking options')
        for group in args.mark:
            marks.append([])
            nodes.append([])
            group = group.replace(',,,', '@;;;@')
            group = group.replace(',,', '@;;@')
            group = group.replace(',', '@;@')
            for mark, subgroup in enumerate(group.split('@;@'), 1):
                if '@;;' in subgroup:
                    node1, node2 = subgroup.split('@;;;@' if '@;;;@' in
                                                  subgroup else '@;;@')
                    node1 = get_node(tree, node1)
                    node2 = get_node(tree, node2)
                    anc = tree.get_common_ancestor(node1, node2)
                    # mark from ancestor
                    if '@;;;@' in subgroup:
                        for node in anc.get_descendants() + [anc]:
                            marks[-1].append('#' + str(mark))
                            nodes[-1].append(node.node_id)
                    # mark at ancestor
                    elif '@;;@' in subgroup:
                        marks[-1].append('#' + str(mark))
                        nodes[-1].append(anc.node_id)
                # mark in single node
                else:
                    node = get_node(tree, subgroup)
                    marks[-1].append('#' + str(mark))
                    nodes[-1].append(node.node_id)
    # mark all leaves successively
    if args.mark_leaves:
        if args.mark:
            exit('ERROR: incompatible marking options')
        marks.extend([['#1'] for n in tree.iter_leaves()])
        nodes.extend([[n.node_id] for n in tree.iter_leaves()])
    # mark all internal branches successively
    if args.mark_internals:
        if args.mark:
            exit('ERROR: incompatible marking options')
        marks.extend(['#1' for s in tree.iter_leaves() if not s.is_leaf()
                      for n in s.iter_descendants()])
        nodes.extend([n.node_id for s in tree.iter_leaves() if not s.is_leaf()
                      for n in s.iter_descendants()])
        marks.extend(['#1' for s in tree.iter_leaves() if not s.is_leaf()])
        nodes.extend([s.node_id for s in tree.iter_leaves() if not s.is_leaf()])
    return nodes, marks

def local_run_model(tree, model_name, binary, ctrl_string='', **kwargs):
    '''
    local verison of model runner. Needed for multiprocessing pickling...
    '''
    def clean_exit(a, b):
        if proc:
            print("Killing process %s" %proc)
            proc.terminate()
            proc.kill(-9)
        sys.exit(a, b)
    proc = None
    signal.signal(signal.SIGINT, clean_exit)


    model_obj = Model(model_name, tree, **kwargs)
    fullpath = os.path.join (tree.workdir, model_obj.name)
    os.system("mkdir -p %s" % fullpath)
    # write tree file
    tree._write_algn(fullpath + '/algn')
    if model_obj.properties['exec'] == 'Slr':
        tree.write(outfile=fullpath+'/tree', format = (11))
    else:
        tree.write(outfile=fullpath+'/tree',
                   format = (10 if model_obj.properties['allow_mark'] else 9))
    # write algn file
    if ctrl_string == '':
        ctrl_string = model_obj.get_ctrl_string(fullpath+'/tmp.ctl')
    else:
        open(fullpath+'/tmp.ctl', 'w').write(ctrl_string)
    hlddir = os.getcwd()
    os.chdir(fullpath)

    proc = Popen("%s tmp.ctl" %binary, stdout=PIPE, shell=True)

    job, err = proc.communicate()
    if err is not None or b'error' in job or b'Error' in job:
        print("ERROR: inside CodeML!!\n" + job)
        return (None, None)
    os.chdir(hlddir)
    return os.path.join(fullpath,'out'), model_obj


def check_done(tree, modmodel, results):
    if os.path.exists(os.path.join(tree.workdir, modmodel, 'out')):
        if modmodel != "SLR":
            fhandler = open(os.path.join(tree.workdir, modmodel, 'out'))
            fhandler.seek(-50, 2)
            if 'Time used' in fhandler.read():
                print('Model %s already executed... SKIPPING' % modmodel)
                results.append((os.path.join(tree.workdir, modmodel, "out"),
                                modmodel))
                return True
        else:
            if os.path.getsize(os.path.join(tree.workdir, modmodel, 'out')) > 0:
                print('Model %s already executed... SKIPPING' % modmodel)
                return True
    return False

def run_all_models(tree, nodes, marks, args, **kwargs):
    ## TO BE IMPROVED: multiprocessing should be called in a simpler way
    print("\nRunning CodeML/Slr (%s CPUs)" %args.maxcores)
    pool = Pool(args.maxcores or None, init_worker)
    results = []
    for model in args.models:
        binary = (os.path.expanduser(args.slr_binary) if model == 'SLR'
                  else os.path.expanduser(args.codeml_binary))
        print('  - processing model %s' % model)
        if AVAIL[model.split('.')[0]]['allow_mark']:
            if not marks:
                if check_done(tree, model, results):
                    continue
                results.append(pool.apply_async(
                    local_run_model, args=(tree, model, binary), kwds=kwargs))
                continue
            for mark, node in zip(marks, nodes):
                print('       marking branches %s\n' %
                      ', '.join([str(m) for m in node]))
                clean_tree(tree)
                tree.mark_tree(node, marks=mark)
                modmodel = model + '.' + '_'.join([str(n) for n in node])
                if check_done(tree, modmodel, results):
                    continue
                print('          %s\n' % (
                    tree.write()))
                results.append(pool.apply_async(
                    local_run_model, args=(tree, modmodel, binary), kwds=kwargs))
        else:
            if check_done(tree, model, results):
                continue
            results.append(pool.apply_async(
                local_run_model, args=(tree, model, binary), kwds=kwargs))

    pool.close()
    pool.join()

    models = {}
    # join back results to tree
    for result in results:
        try:
            path, model_obj = result.get()
            models[model_obj.name] = path
        except AttributeError:
            path, model = result
            models[result[1]] = result[0]
    return models

def reformat_nw(nw_path):
    """
    Clean tree file in order to make it look more like standard newick.
    Replaces PAML marks to match NHX format
    """
    if os.path.exists(nw_path):
        file_string = open(nw_path).read()
        beg = file_string.index('(')
        end = file_string.index(';')
        file_string = re.sub("'(#[0-9]+)'", "[&&NHX:mark=\\1]",
                             file_string[beg:end + 1])
        return file_string
    return nw_path

####### PROPOSAL FOR A BETTER MULTIPROCESSING ############
results_queue = Queue()
def run_all_models_new(tree, nodes, marks, args, **kwargs):
    pool = Pool(args.maxcores or None)
    results = []
    commands = []
    for model in args.models:
        binary = args.slr_binary if model == 'SLR' else args.codeml_binary
        if AVAIL[model.split('.')[0]]['allow_mark']:
            for mark, node in zip(marks, nodes):
                clean_tree(tree)
                tree.mark_tree(node, marks=mark)
                modmodel = model + '.' + '_'.join([str(n) for n in node])
                if check_done(tree, modmodel, results):
                    continue
                else:
                    commands.append((tree, modmodel, binary, kwargs))
        else:
            if check_done(tree, model, results):
                continue
            else:
                commands.append((tree, model, binary, kwargs))
    print("Running CODEML/SLR (%s CPUs)" %(args.maxcores))
    for c in commands:
        print("  %s, %s" %(c[1], kwargs))

    pool.map(local_run_model_new, commands)
    models = {}
    while not results_queue.empty():
        path, model_name = results_queue.get()
        models[model_name] = path
    return models

def local_run_model_new(arguments,  ctrl_string=''):
    def clean_exit(a, b):
        print(a, b)
        if proc:
            print("Killing %s" %proc)
            proc.kill(-9)
        sys.exit(a, b)
    proc = None
    signal.signal(signal.SIGINT, clean_exit)

    tree, model_name, binary, kwargs = arguments

    model_obj = Model(model_name, tree, **kwargs)

    fullpath = os.path.join (tree.workdir, model_obj.name)

    os.system("mkdir -p %s" % fullpath)

    # write tree file
    tree._write_algn(fullpath + '/algn')
    if model_obj.properties['exec'] == 'Slr':
        tree.write(outfile=fullpath+'/tree', format = (11))
    else:
        tree.write(outfile=fullpath+'/tree',
                   format = (10 if model_obj.properties['allow_mark'] else 9))

    # write algn file
    if ctrl_string == '':
        ctrl_string = model_obj.get_ctrl_string(fullpath+'/tmp.ctl')
    else:
        open(fullpath+'/tmp.ctl', 'w').write(ctrl_string)
    hlddir = os.getcwd()
    os.chdir(fullpath)

    proc = Popen("%s tmp.ctl" %binary, stdout=PIPE, shell=True)

    job, err = proc.communicate()
    if err is not None or b'error' in job or b'Error' in job:
        raise ValueError("ERROR: inside codeml!!\n" + job)

    results_queue.put((os.path.join(fullpath,'out'), model_obj.name))
#############

def load_model(model_name, tree, path, **kwargs):
    model_obj = Model(model_name, tree, **kwargs)
    setattr(model_obj, 'run', run)
    #try:
    tree.link_to_evol_model(path, model_obj)
    #except KeyError:
    #    warn('ERROR: model %s failed' % (model_obj.name))

def write_results(tree, args):
    tests = "\nLRT\n\n"
    tests += ('%25s |%25s | %s\n' % ('Null model', 'Alternative model',
                                     'p-value'))
    tests += (' ' * 5 + ('-' * 60))
    tests += ('\n')
    at_least_one_come_on = False
    results = {}
    if args.tests != 'auto':
        wanted = [t.split(',') for t in args.tests]
    else:
        wanted = []
    bests = []
    for null in tree._models:
        for altn in tree._models:
            if tree._models[null].np >= tree._models[altn].np:
                continue
            if null == 'SLR' or altn == 'SLR':
                continue
            # we usually want to compare models of the same kind
            if (((AVAIL[null.split('.')[0]]['typ']=='site' and
                  AVAIL[altn.split('.')[0]]['typ']=='branch') or
                 (AVAIL[altn.split('.')[0]]['typ']=='site' and
                  AVAIL[null.split('.')[0]]['typ']=='branch'))
                and args.tests == 'auto'):
                continue
            # we usually want to compare models marked in the same way
            if (('.' in altn and '.' in null) and
                (altn.split('.')[1] != null.split('.')[1])):
                continue
            if args.tests != 'auto':
                if not any([(null.split('.')[0] in test and
                             altn.split('.')[0] in test)
                            for test in wanted]):
                    continue
            results[(null, altn)] = tree.get_most_likely(altn, null)
            bests.append(null if results[(null, altn)] > 0.05 else altn)

            tests += ('%25s |%25s | %f%s\n' % (
                null, altn, results[(null, altn)],
                '**' if results[(null, altn)] < 0.01 else '*'
                if results[(null, altn)] < 0.05 else ''))
            at_least_one_come_on = True

    if at_least_one_come_on:
        print(tests)
    return bests

def run(args):
    if not args.slr_binary:
        args.slr_binary = find_binary("Slr")
    if not args.codeml_binary:
        args.codeml_binary = find_binary("codeml")

    binary  = os.path.expanduser(args.slr_binary)
    if not os.path.exists(binary):
        print("Warning: SLR binary does not exist at %s" % args.slr_binary,
              file=sys.stderr)
        print("         provide another route with --slr_binary, or install "
              "it by executing 'ete3 install-external-tools paml'",
              file=sys.stderr)
    binary  = os.path.expanduser(args.codeml_binary)
    if not os.path.exists(binary):
        print("Warning: CodeML binary does not exist at %s" % args.codeml_binary,
              file=sys.stderr)
        print("         provide another route with --codeml_binary, or install "
              "it by executing 'ete3 install-external-tools paml'",
              file=sys.stderr)

    # more help
    # TODO: move this to help section
    if args.super_help:
        help_str = ('Description of CodeML parameters, see PAML manual for more '
                    'information\n\n')
        for key in PARAMS_DESCRIPTION:
            help_str += ('  - %-12s: %s\n' % (key, ''.join([
                PARAMS_DESCRIPTION[key][i:i + 70] + '\n' + ' ' * 18
                for i in range(0, len(PARAMS_DESCRIPTION[key]), 70)])))
        os.system('echo "%s" | less' % help_str)
        return

    # in case we only got 1 model :(
    if isinstance(args.models, str):
        args.models = [args.models]

    params = {}
    if args.config_file:
        if args.params:
            print('WARNING: input CodeML parameters from configuration file will'
                 ' be overridden by the ones in the command line')
        params = parse_config_file(args.config_file)
        if 'seqfile' in params:
            args.alg = os.path.join(os.path.split(args.config_file)[0],
                                    params['seqfile'])
            del(params['seqfile'])
        if 'outfile' in params:
            if not args.output:
                args.output = os.path.join(os.path.split(args.config_file)[0],
                                           params['outfile'])
            else:
                print('WARNING: input CodeML output file from configuration file'
                     ' will be overridden by the one in the command line')
            del(params['outfile'])
        if 'treefile' in params:
            if not args.src_trees:
                args.src_tree_iterator = [os.path.join(
                    os.path.split(args.config_file)[0],
                    params['treefile'])]
            else:
                args.src_tree_iterator = list(args.src_tree_iterator)
                print('WARNING: input CodeML tree file from configuration file'
                     ' will be overridden by the one in the command line')
            del(params['treefile'])
        try:
            if len(args.models) > 1 or not args.models[0].startswith('XX.'):
                raise Exception('ERROR: only 1 model name starting with "XX." '
                                'can be used with a configuration file.')
        except TypeError:
            args.models = ['XX.' + os.path.split(args.config_file)[1]]
    for nw in args.src_tree_iterator:
        tree = EvolTree(reformat_nw(nw), format=1)
        if args.output:
            tree.workdir = args.output
        if args.clear_all:
            Popen('rm -rf %s' % tree.workdir, shell=True).communicate()

        if args.node_ids:
            print('\n%-7s : %s' % ("Node ID", "Leaf name"))
            print('-'*50)
            for n in tree.iter_leaves():
                print('   %-4s : %s' % (n.node_id, n.name))
            print('\n%-7s : %s' % ("Node ID", "Descendant leaves names"))
            print('-'*50)
            for n in tree.iter_descendants():
                if n.is_leaf():
                    continue
                print('   %-4s : %s' % (n.node_id, ', '.join(
                    [l.name for l in n.iter_leaves()])))
            print('\n   %-4s : %s' % (tree.node_id, 'ROOT'))
            return

        # get the marks we will apply to different runs
        nodes, marks = get_marks_from_args(tree, args)
        # link to alignment
        tree.link_to_alignment(args.alg, alg_format='paml')
        # load models
        models = {}
        if args.prev_models:
            models = dict([(m.split(',')[1], m.split(',')[0] + '/out')
                           for m in args.prev_models])
        # run models
        if args.models:
            for p in args.params:
                p, v = p.split(',')
                try:
                    v = int(v)
                except ValueError:
                    try:
                        v = float(v)
                    except ValueError:
                        pass
                params[p] = v
            models.update(run_all_models(tree, nodes, marks, args, **params))
        # link models to tree
        params = {}
        for model in models:
            load_model(model, tree, models[model], **params)
        # print results
        bests = write_results(tree, args)
        # apply evol model (best branch model?) to tree for display
        # TODO: best needs to be guessed from LRT
        try:
            best = max([m for m in bests
                        if AVAIL[m.split('.')[0]]['typ']=='branch'],
                       key=lambda x: tree._models[x].lnL)
            tree.change_dist_to_evol('bL', tree._models[best], fill=True)
        except ValueError:
            best = None

        # get all site models for display
        site_models = [m for m in tree._models
                       if 'site' in AVAIL[m.split('.')[0]]['typ']]

        if args.noimg:
            return

        if args.histface:
            if len(args.histface) != len(site_models):
                if len(args.histface) == 1:
                    args.histface = args.histface * len(site_models)
                elif len(args.histface) <= len(site_models):
                    args.histface.extend([args.histface[-1]] * (
                        len(site_models) - len(args.histface)))
                else:
                    print('WARNING: not using last histfaces, not enough models')
                    args.histface = args.histface[:len(site_models)]
            for num, (hist, model) in enumerate(
                zip(args.histface, site_models)):
                model = tree.get_evol_model(model)
                model.set_histface(up=not bool(num),
                                   kind=hist.replace('+-', ''),
                                   errors='+-' in hist)
        if args.show:
            tree.show(histfaces=site_models,
                      layout=evol_clean_layout if args.clean_layout else None)
        else:
            tree.render(os.path.join(tree.workdir, 'tree_%s%s.pdf' % (
                'hist-%s_' % ('-'.join(site_models)) if site_models else '',
                best)), histfaces=site_models,
                        layout=evol_clean_layout if args.clean_layout else None)

