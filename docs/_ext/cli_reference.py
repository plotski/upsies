import subprocess

from docutils import nodes
from sphinx.util.docutils import SphinxDirective

from upsies import __project_name__
from upsies.uis.tui.commands import CommandBase
from upsies.utils import subclasses, submodules


class CliReference(SphinxDirective):
    has_content = True

    def run(self):
        nodelist = [
            nodes.literal_block(text=self._run_cmd(('upsies', '--version')), language='none'),
            nodes.literal_block(text=self._run_cmd(('upsies', '--help')), language='none'),
        ]

        for module_path in self.content:
            subcmdclses = self._get_CommandBase_subclasses(module_path)
            for subcmdcls in subcmdclses:
                # Subcommand
                section = self._get_subcmd_section(
                    subcmd_names=subcmdcls.names,
                    args=('--help',),
                )
                nodelist.append(section)

                # Subsubcommands
                for subsubcmd_name in sorted(subcmdcls.subcommands):
                    section = self._get_subcmd_section(
                        subcmd_names=subcmdcls.names,
                        subsubcmd_names=(subsubcmd_name,),
                        args=('--help',),
                    )
                    nodelist.append(section)

        return nodelist

    def _get_CommandBase_subclasses(self, module_path):
        return sorted(
            subclasses(CommandBase, submodules(module_path)),
            key=lambda subcmdcls: subcmdcls.names[0],
        )

    def _get_subcmd_section(self, subcmd_names, subsubcmd_names=(), args=()):
        title = self._join_cmd_names(subcmd_names)
        argv = (__project_name__, subcmd_names[0])
        ids = subcmd_names[0]
        if subsubcmd_names:
            title += ' ' + self._join_cmd_names(subsubcmd_names)
            argv += (subsubcmd_names[0],)
            ids += '-' + subsubcmd_names[0]
        argv += tuple(args)

        section = nodes.section(ids=[ids])
        section += nodes.title(text=title)
        section += nodes.literal_block(
            text=self._run_cmd(argv),
            language='none',
        )
        return section

    def _join_cmd_names(self, names):
        joined = names[0]
        if len(names) >= 2:
            joined += ' (' + ', '.join(names[1:]) + ')'
        return joined

    def _run_cmd(self, argv):
        proc = subprocess.run(
            argv,
            encoding='utf-8',
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        return '$ ' + ' '.join(argv) + '\n' + proc.stdout


def setup(app):
    app.add_directive('cli_reference', CliReference)
    return {
        'version': '0.1',
        'parallel_read_safe': True,
        'parallel_write_safe': True,
    }
