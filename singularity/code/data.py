# file: data.py
# Copyright (C) 2008 FunnyMan3595
# This file is part of Endgame: Singularity.

# Endgame: Singularity is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

# Endgame: Singularity is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Endgame: Singularity; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# This file contains all data loading functions.

from __future__ import absolute_import


import os
import sys
import collections
from configparser import RawConfigParser
from io import open

from singularity.code import g, i18n
from singularity.code import dirs
from singularity.code import (
    group,
    base,
    tech,
    item,
    event,
    location,
    difficulty,
    task,
    region,
    warning,
)
import singularity.code.graphics.theme as theme


def generic_load(filename, load_dirs="data", mandatory=True, no_list=False):
    """
    generic_load() loads a data file.  Data files are all in Python-standard
    ConfigParser format.  The 'id' of any object is the section of that object.
    Fields that need to be lists are postpended with _list; this is stripped
    from the actual name, and the internal entries are broken up by the pipe
    ("|") character.

    On errors, if file is mandatory then quit, else raise exception. For syntax
    parsing-related errors, always print error message. For IOErrors silently ignore
    non-mandatory missing or otherwise unreadable files"""

    # Get directories to find the file
    if load_dirs is not None:
        load_dirs = dirs.get_read_dirs(load_dirs)

    # For each directories, create a file, otherwise use filename
    if load_dirs is not None:
        files = [os.path.join(load_dir, filename) for load_dir in load_dirs]
    else:
        files = [filename]

    # Find the first readable file.
    found = False
    errors = []
    config = RawConfigParser()

    for filepath in files:
        try:
            with open(filepath, encoding="utf-8") as fd:
                config.read_file(fd)
            found = True
            break

        except IOError as reason:
            # Silently ignore non-mandatory missing files
            if mandatory:
                errors.append("Cannot read '%s': %s\nExiting\n" % (filename, reason))

        except Exception as reason:
            # Always print parsing errors, even for non-mandatory files
            errors.append("Error parsing '%s': %s\n" % (filename, reason))

    for err in errors:
        sys.stderr.write(err)

    if not found:
        if mandatory:
            sys.exit(1)
        else:
            return

    return_list = []

    # Get the list of items (IDs) in the file and loop through them.
    for item_id in config.sections():
        item_dict = {}
        item_dict["id"] = item_id

        # Get the list of settings for this particular item.
        for option in config.options(item_id):
            # If this is a list ...
            if not no_list and (len(option) > 6 and option[-5:] == "_list"):
                # Break it into elements separated by |.
                item_dict[option[:-5]] = [
                    x.strip() for x in config.get(item_id, option).split("|")
                ]
            else:
                # Otherwise, just grab the data.
                item_dict[option] = config.get(item_id, option).strip()

        # Add this to the list of all objects we are returning.
        return_list.append(item_dict)

    return return_list


def parse_spec_from_file(spec_cls, filename):
    spec_data = generic_load(filename)
    for element_no, spec_data in enumerate(spec_data, 1):
        try:
            spec_id = spec_data["id"]
        except KeyError:  # pragma: no cover
            sys.stderr.write(
                "Data element %d in file %s has no ID!?" % (element_no, filename)
            )
            sys.exit(1)

        yield spec_cls.create_from_data_file(spec_id, spec_data)


def check_required_fields(dict, fields, name="Unknown type"):
    """
    check_required_fields() will check for the existence of every field in
    the list 'fields' in the dictionary 'dict'.  If any do not exist, it
    will print an error message and abort.  Part of that error message is
    the type of object it is processing; this should be passed in via 'name'."""
    for field in fields:
        if field not in dict:
            sys.stderr.write("%s %s lacks key %s.\n" % (name, repr(dict), field))
            sys.exit(1)


def load_generic_defs_file(name, no_list=True):
    filepath = dirs.get_readable_file_in_dirs(name + "_str.dat", "data")

    return generic_load(filepath, mandatory=True, no_list=no_list)


def load_generic_defs(name, object_list, listttype_attrs=frozenset()):
    item_list = load_generic_defs_file(name)
    for data_item in item_list:
        item_id = data_item["id"]
        obj = object_list[item_id]

        for key_dat_file in data_item:
            if key_dat_file == "id":
                continue

            key_name = key_dat_file
            if len(key_dat_file) > 6 and key_dat_file.endswith("_list"):
                key_name = key_dat_file[:-5]

                if key_name not in listttype_attrs:
                    # Not allowed to be a list; revert to the original name
                    key_name = key_dat_file

            if not hasattr(obj, key_name):
                continue

            # Translations use the field name as defined in the data file (and not
            # the field name of the object)
            tr = get_def_translation(item_id, key_dat_file, data_item[key_dat_file])

            if key_name in listttype_attrs:
                setattr(obj, key_name, [x.strip() for x in tr.split("|")])
            else:
                setattr(obj, key_name, tr)


def get_def_translation(object_id, field, text):
    ctxt = "[" + object_id + "] " + field
    return g.data_strings.get((ctxt, text), text)


def load_significant_numbers():
    significant_numbers = g.significant_numbers = []

    numbers_file = dirs.get_readable_file_in_dirs("numbers.dat", "data")

    if numbers_file is None:
        sys.stderr.write("WARNING: Cannot read file: numbers.dat\n")
        return

    with open(numbers_file, "r", encoding="utf-8") as file:
        for index, line in enumerate(file):
            value = line.split("#")[0].strip()

            if len(value) == 0:
                continue

            try:
                number = int(value)
                significant_numbers.append(number)
            except ValueError:
                sys.stderr.write(
                    "WARNING: Invalid number in 'numbers.dat' line: %d\n" % index
                )


def load_internal_id():
    internal_id_file = dirs.get_readable_file_in_dirs("internal_id.dat", "data")

    g.internal_id_forward = {}
    g.internal_id_backward = {}

    with open(internal_id_file, "r", encoding="utf-8") as file:
        for index, line in enumerate(file):
            line = line.strip()

            if len(line) == 0 or line[0] == "#":
                continue

            try:
                obj, internal_id = line.split("=")
                obj_type, obj_id = obj.split("|")

                internal_id = internal_id.strip()
                obj_type = obj_type.strip()
                obj_id = obj_id.strip()

                if obj_type not in g.internal_id_forward:
                    g.internal_id_forward[obj_type] = {}
                    g.internal_id_backward[obj_type] = {}

                if obj_id in g.internal_id_forward[obj_type]:
                    sys.stderr.write(
                        "WARNING: Overwrite internal ID in 'internal_id.dat' line: %d\n"
                        % index
                        + 1
                    )
                    sys.exit(1)

                g.internal_id_forward[obj_type][obj_id] = internal_id
                g.internal_id_backward[obj_type][internal_id] = obj_id

            except ValueError:
                sys.stderr.write(
                    "WARNING: Invalid internal ID in 'internal_id.dat' line: %d\n"
                    % index
                    + 1
                )
                sys.exit(1)


def load_groups_defs():
    load_generic_defs("groups", g.groups)


def load_groups():
    groups = g.groups = collections.OrderedDict()

    for group_spec in parse_spec_from_file(group.GroupSpec, "groups.dat"):
        groups[group_spec.id] = group_spec

    load_groups_defs()


def load_base_defs():
    load_generic_defs("bases", g.base_type, listttype_attrs={"flavor"})


def load_bases():
    g.base_type = {
        base_spec.id: base_spec
        for base_spec in parse_spec_from_file(base.BaseSpec, "bases.dat")
    }

    load_base_defs()


class Danger(object):
    def __init__(self, id, untranslated_research_desc, untranslated_knowledge_desc):
        self.id = id
        self.untranslated_research_desc = untranslated_research_desc
        self.untranslated_knowledge_desc = untranslated_knowledge_desc

    def _translate(self, field, string):
        return get_def_translation(self.id, field, string)

    @property
    def research_desc(self):
        return self._translate("research_desc", self.untranslated_research_desc)

    @property
    def knowledge_desc(self):
        return self._translate("knowledge_desc", self.untranslated_knowledge_desc)


def load_danger():
    dangers = g.dangers = {}

    danger_list = load_generic_defs_file("dangers")

    for danger_def in danger_list:
        check_required_fields(
            danger_def, ("id", "research_desc", "knowledge_desc"), "Danger"
        )

        danger_id = danger_def["id"]

        if not danger_id.startswith("danger_"):
            sys.stderr.write("Invalid format for danger id: %s\n" % danger_id)
            sys.exit(1)

        danger_level = int(danger_id[7:])

        dangers[danger_level] = Danger(
            danger_id, danger_def["research_desc"], danger_def["knowledge_desc"]
        )


def load_regions():
    regions = g.regions = {}

    region_infos = generic_load("regions.dat")

    for region_info in region_infos:
        # Certain keys are absolutely required for each entry.  Make sure
        # they're there.
        check_required_fields(region_info, ("id",), "Region")

        id = region_info["id"]

        modifiers_list = []

        i = 0
        while True:
            i += 1
            modifiers_name = "modifier%d" % i
            if modifiers_name not in region_info:
                break

            modifiers_dict = g.read_modifiers_dict(region_info.get(modifiers_name, []))
            modifiers_list.append(modifiers_dict)

        regions[id] = region.RegionSpec(id, modifiers_list)


def load_location_defs():
    load_generic_defs("locations", g.locations, listttype_attrs={"cities"})


def load_locations():
    regions = g.regions

    locations = g.locations = {
        loc_spec.id: loc_spec
        for loc_spec in parse_spec_from_file(location.LocationSpec, "locations.dat")
    }

    for loc_spec in locations.values():
        # Add the location to regions it is in them.
        for region_id in loc_spec.regions:
            if region_id not in regions:
                sys.stderr.write("Error with region given: %s\n" % repr(region_id))
                sys.exit(1)
            regions[region_id].locations.append(loc_spec.id)

    load_location_defs()


def load_tech_defs():
    load_generic_defs("techs", g.techs)


def load_techs():
    g.techs = {
        tech_spec.id: tech_spec
        for tech_spec in parse_spec_from_file(tech.TechSpec, "techs.dat")
    }

    if g.debug:  # pragma: no cover
        print("Loaded %d techs." % len(g.techs))

    load_tech_defs()


def load_item_types():
    item.item_types = collections.OrderedDict()

    for item_type in parse_spec_from_file(item.ItemType, "itemtypes.dat"):
        item.item_types[item_type.id] = item_type

    load_item_type_defs()


def load_item_type_defs():
    load_generic_defs("itemtypes", item.item_types)


def load_items():
    g.items = {
        item_spec.id: item_spec
        for item_spec in parse_spec_from_file(item.ItemSpec, "items.dat")
    }

    load_item_defs()


def load_item_defs():
    load_generic_defs("items", g.items)


def load_events():
    g.events = {
        event_spec.id: event_spec
        for event_spec in parse_spec_from_file(event.EventSpec, "events.dat")
    }
    load_event_defs()


def load_event_defs():
    load_generic_defs("events", g.events)


def load_tasks():
    tasks = g.tasks = collections.OrderedDict()  # Keep order (important)

    task_list = generic_load("tasks.dat")
    for task_dict in task_list:
        # Certain keys are absolutely required for each entry.  Make sure
        # they're there.
        check_required_fields(task_dict, ("id", "type"), "Task")

        task_id = task_dict["id"]
        task_type = task_dict["type"]

        # Only jobs and cpu_pool are possible for now
        if task_type == "jobs":
            task_value = int(task_dict["value"])
            # Make sure prerequisites, if any, are lists.
            task_pre = task_dict.get("pre", [])
            if type(task_pre) != list:
                task_pre = [task_pre]

        elif task_type == "cpu_pool":
            task_value = 0
            task_pre = []

        else:
            sys.stderr.write("Only jobs and cpu_pool task are supported\n")
            sys.exit(1)

        tasks[task_id] = task.Task(task_id, task_type, task_value, task_pre)

    if all(
        len(t.prerequisites) > 0 for t in (tasks[k] for k in tasks) if t.type == "jobs"
    ):
        sys.stderr.write(
            "A minimun of one job task without prerequisite is needed for the game\n"
        )
        sys.exit(1)

    for t in g.tasks.values():
        g.tasks_by_type[t.type].append(t)

    task.tasks_reset()

    load_task_defs()


def load_task_defs():
    load_generic_defs("tasks", g.tasks)


def load_theme(theme_id, theme_dir):
    new_theme = theme.Theme(theme_id, theme_dir)

    for variant, filename in new_theme.search_variant():
        theme_list = generic_load(filename, load_dirs=None)

        variant_theme = theme.VariantTheme(variant)
        new_theme.set_variant(variant_theme)

        for theme_section in theme_list:
            if theme_section["id"] == "general":
                variant_theme.name = theme_section["name"]

                if "parent" in theme_section:
                    if variant is None:
                        new_theme.inherit(theme_section["parent"])
                    else:
                        sys.stderr.write(
                            "Cannot override parent in variant theme '%s'"
                            % repr(filename)
                        )

            if theme_section["id"] == "fonts":
                for key in theme_section:
                    if key == "id":
                        continue
                    variant_theme.set_font(key, theme_section[key])

            if theme_section["id"] == "colors":
                for key in theme_section:
                    if key == "id":
                        continue
                    variant_theme.set_color(key, theme_section[key])

    return new_theme


def load_themes():
    themes = theme.themes = {}
    themes_dirs = dirs.get_read_dirs("themes")

    for themes_dir in themes_dirs:
        themes_list = [
            name
            for name in os.listdir(themes_dir)
            if os.path.isdir(os.path.join(themes_dir, name))
        ]

        for theme_id in themes_list:
            if theme_id in themes:
                continue

            th = load_theme(theme_id, os.path.join(themes_dir, theme_id))
            th.find_files()
            themes[theme_id] = th


def load_difficulties():
    difficulties = difficulty.difficulties = collections.OrderedDict()

    for diff in parse_spec_from_file(difficulty.Difficulty, "difficulties.dat"):
        difficulties[diff.id] = diff

    load_difficulty_defs()


def load_difficulty_defs():
    load_generic_defs("difficulties", difficulty.difficulties)


def load_knowledge():
    knowledge = g.knowledge = {}

    from singularity.code.knowledge import KnowledgeHelpEntry, KnowledgeArea

    help_list = load_generic_defs_file("knowledge", no_list=False)
    for help_section in help_list:
        knowledge_id = help_section["id"]
        help_entries = {}

        # Load the knowledge lists.
        help_keys = [x for x in help_section if x != "id" and x != "name"]
        for help_key in help_keys:
            help_entry = help_section[help_key]
            if type(help_entry) != list or len(help_entry) != 2:
                sys.stderr.write("Invalid knowledge entry %s." % repr(help_entry))
                sys.exit(1)

            help_entries[help_key] = KnowledgeHelpEntry(
                knowledge_id, help_key, help_entry[0], help_entry[1]
            )

        knowledge[knowledge_id] = KnowledgeArea(
            knowledge_id, help_section["name"], help_entries
        )


def load_warning_defs():
    warning.warnings["cpu_usage"].name = _("Do not use all the available CPU.")
    warning.warnings["cpu_usage"].message = _(
        "I didn't use all the available processor power. I will use the CPU time left to work whatever Jobs I can."
    )
    warning.warnings["one_base"].name = _("Only one base remaining.")
    warning.warnings["one_base"].message = _(
        "Only one base can hold my conscience. I am in danger to lose the last place left to survive."
    )
    warning.warnings["cpu_pool_zero"].name = _("CPU POOL is empty.")
    warning.warnings["cpu_pool_zero"].message = _(
        "My cpu pool is empty. Some of my bases or items cannot be build without CPU."
    )
    warning.warnings["cpu_maintenance"].name = _("CPU POOL not enough for maintenance.")
    warning.warnings["cpu_maintenance"].message = _(
        "My cpu pool is not enough to maintain some of my bases. I may lose them."
    )


def load_strings():
    load_story_defs()
    load_warning_defs()


class StorySectionPart(object):
    def __init__(self, msgctxt, text, translator_comments):
        self.msgctxt = msgctxt
        self.text = text
        self.translator_comments = translator_comments


def load_story_defs():
    story = g.story = {}

    story_file_path = dirs.get_readable_file_in_dirs("story.dat", "data")

    if story_file_path is None:
        print("Story is missing. Skipping.")
        return

    # Take the last story file, story is never partially translated.
    story_file = open(story_file_path, "r", encoding="utf-8")

    section_name = ""
    segment = ""
    translator_comments = ""
    line_num = 1

    for line in story_file.readlines():
        if line and line != "\n":
            if line[0] == "#":
                if line.startswith("# TRANSLATORS:") and section_name:
                    translator_comments += " " + line[14:].strip()
                continue
            elif line[0] == "[":
                if line[-2] == "]":
                    section_name = line[1:-2]
                    story[section_name] = []
                else:
                    sys.stderr.write(
                        "Line start with [ and is not a section at line %d.\n"
                        % line_num
                    )
            elif line[0] == "|":
                segment += line[1:]
            else:
                # TODO: Parse command
                sys.stderr.write("Invalid command at line %d.\n" % line_num)
        else:
            if segment:
                parts = story[section_name]
                ctxt = "[Story section] %s (%d)" % (section_name, len(parts) + 1)
                parts.append(
                    StorySectionPart(ctxt, segment, translator_comments.strip())
                )
                segment = ""
                translator_comments = ""

        line_num += 1

    # Add last segment.
    if segment:
        parts = story[section_name]
        ctxt = "[Story section] %s (%d)" % (section_name, len(parts) + 1)
        parts.append(StorySectionPart(ctxt, segment, translator_comments.strip()))


def reload_all():
    load_internal_id()
    load_danger()
    load_significant_numbers()
    load_strings()
    load_groups()
    load_knowledge()
    load_difficulties()
    load_tasks()
    load_events()
    load_regions()
    load_locations()
    load_techs()
    load_item_types()
    load_items()
    load_bases()


def reload_all_def():
    load_strings()
    load_groups_defs()
    load_difficulty_defs()
    load_base_defs()
    load_tech_defs()
    load_item_type_defs()
    load_item_defs()
    load_event_defs()
    load_task_defs()
    load_location_defs()


def reload_all_mutable_def():
    # Apply current language
    load_tech_defs()
    load_location_defs()
    load_event_defs()
