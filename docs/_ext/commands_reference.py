import logging
import subprocess

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.statemachine import ViewList
from sphinx.util.docutils import SphinxDirective

from upsies import __project_name__, __version__
from upsies.uis.tui.commands import CommandBase
from upsies.utils import subclasses, submodules


class CommandsReference(SphinxDirective):
    has_content = True

    def run(self):
        help_list = nodes.bullet_list()
        nodelist = [
            nodes.paragraph(text=(
                f"This page lists help screen for {__project_name__} {__version__}."
            )),
            help_list,
        ]

        for module_path in self.content:
            cmdclses = self._get_CommandBase_subclasses(module_path)
            for cmdcls in cmdclses:
                subcmd_name = cmdcls.names[0]
                help_cmd = f'{__project_name__} {subcmd_name} --help'
                help_text = self._get_cmd_output(help_cmd)
                paragraph = nodes.paragraph()
                paragraph += nodes.strong(text=subcmd_name)
                paragraph += nodes.literal_block(text=help_text, language='none')
                help_list += nodes.list_item('', paragraph)

        return nodelist

    def _get_CommandBase_subclasses(self, module_path):
        return sorted(
            subclasses(CommandBase, submodules(module_path)),
            key=lambda subcmdcls: subcmdcls.names[0],
        )

    def _get_cmd_output(self, cmd):
        proc = subprocess.run(
            cmd,
            encoding='utf-8',
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return proc.stdout


def setup(app):
    app.add_directive('commands_reference', CommandsReference)
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
