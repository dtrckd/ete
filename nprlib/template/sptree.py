import os
import numpy 
import re
import commands
import logging
import numpy
from collections import defaultdict

from nprlib.task import ConcatAlg, BrhCogSelector
from nprlib.errors import DataError
from nprlib.utils import GLOBALS, generate_runid, SeqGroup
from nprlib import db
from nprlib.master_task import register_task_recursively

log = logging.getLogger("main")

n2class = {
    "none": None, 
    "concat_alg": ConcatAlg, 
    }

def process_task(task, conf, nodeid2info):
    seqtype = task.seqtype
    nodeid = task.nodeid
    ttype = task.ttype
    node_info = nodeid2info[nodeid]
    size = task.size
    target_seqs = node_info.get("target_seqs", [])
    out_seqs = node_info.get("out_seqs", [])
    constrain_tree = None
    constrain_tree_path = None
    if out_seqs and len(out_seqs) > 1:
        constrain_tree = "(%s, (%s));" %(','.join(out_seqs), 
                                           ','.join(target_seqs))
      
        constrain_tree_path = os.path.join(task.taskdir, "constrain.nw")
        print constrain_tree

    #print node_info, (size, index, _alg_cleaner, _model_tester, _aligner, _tree_builder)
    new_tasks = []
    if ttype == "cog_selector":
        # register concat alg
        concat_job = ConcatAlg(nodeid, task.cogs, seqtype)
        concat_job.size = task.size
        new_tasks.append(concat_job)
        
    elif ttype == "concat_alg":
        # register concat tree
        pass
    elif ttype == "concat_tree":
        # register concat_Tree split and merge 
        pass
    elif ttype == "concat_tree_merge":
        # for each algjob in cogs, concatenate them and register a new tree task
        pass
    elif ttype == "treemerger":
        # GET NEW NPR NODES
        pass
        #FOR EACH SET OF SPECIES, SELECT COGS AND CREATE A CONCATALG TASK
        pass

    return new_tasks


def pipeline(task):
    conf = GLOBALS["config"]
    nodeid2info = GLOBALS["nodeinfo"]
    if not task:
        #all_seqids = source.id2name.values()
        #sample_cogs = [set(all_seqids), set(all_seqids[:-2]), set(all_seqids[:-3])]
        #initial_task = ConcatAlg("SPTREE_TEST_ID", sample_cogs, set(),
        #                         seqtype=source_seqtype, source=source)
        
        initial_task = BrhCogSelector(GLOBALS["target_species"],
                                      set(), "aa")
                                    
        initial_task.main_tree = main_tree = None
        initial_task.threadid = generate_runid()

        # Register node 
        db.add_node(initial_task.threadid, initial_task.nodeid,
                    initial_task.cladeid, initial_task.target_sp,
                    initial_task.out_sp)
        
        new_tasks = [initial_task]
        conf["_iters"] = 1
    else:
        new_tasks  = process_task(task, conf, nodeid2info)

    # Basic registration and processing of newly generated tasks
    parent_taskid = task.taskid if task else None
    for ts in new_tasks:
        register_task_recursively(ts, parentid=parent_taskid)
        db.add_task2child(parent_taskid, ts.taskid)
        # sort task by nodeid
        nodeid2info[ts.nodeid].setdefault("tasks", []).append(ts)
        if task:
            # Clone processor, in case tasks belong to a side workflow
            ts.task_processor = task.task_processor
            ts.threadid = task.threadid
            ts.main_tree = task.main_tree
            
    return new_tasks
    
config_specs = """

[main]
max_iters = integer(minv=1)
render_tree_images = boolean()

npr_max_seqs = integer_list(minv=0)
npr_min_branch_support = float_list(minv=0, maxv=1)

npr_max_aa_identity = float_list(minv=0.0)

npr_nt_alg_cleaner = list()
npr_aa_alg_cleaner = list()

npr_aa_aligner = list()
npr_nt_aligner = list()

npr_aa_tree_builder = list()
npr_nt_tree_builder = list()

npr_aa_model_tester = list()
npr_nt_model_tester = list()

[tree_splitter]
_min_size = integer()
_max_seq_identity = float()
_outgroup_size = integer()
_outgroup_min_support = float()
_outgroup_topology_dist = boolean()
"""