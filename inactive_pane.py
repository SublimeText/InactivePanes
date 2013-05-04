import os
import shutil
import re

import sublime
import sublime_plugin

ST2 = int(sublime.version()) < 3000

# We have to record the module path when the file is loaded because
# Sublime Text changes it later.
module_path = os.getcwdu() if ST2 else os.path.dirname(__file__)
module_name = os.path.split(module_path)[1]


# Using this convenience function since `sublime.load_settings` will cached anyway.
def Prefs():
    return sublime.load_settings('Preferences.sublime-settings')


class InactivePanes(object):
    """A dummy class which holds this plugin's methods.
    Maybe I can think of a better way to structure plugins like these but for now this'll do it
    """
    def init(self):
        self.enabled    = Prefs().get('fade_inactive_panes', False)
        self.grey_scale = Prefs().get('fade_inactive_panes_grey_scale', .2)
        # Register some callbacks

        def add_on_change(setting, callback):
            Prefs().clear_on_change(setting)
            Prefs().add_on_change(setting, callback)

        add_on_change('fade_inactive_panes_grey_scale', self.on_settings_change)
        add_on_change('fade_inactive_panes',            self.on_settings_change)

        # Reset all panes, eventually the settings changed
        self.cycling_reset()

    def deinit(self):
        Prefs().clear_on_change('fade_inactive_panes_grey_scale')
        Prefs().clear_on_change('fade_inactive_panes')

    def on_settings_change(self):
        if (Prefs().get('fade_inactive_panes', False) != self.enabled
                or Prefs().get('fade_inactive_panes_grey_scale', .2) != self.grey_scale):

            print("[InactivePanes] Settings changed!")

            # Load new settings
            disable = self.enabled and self.enabled != Prefs().get('fade_inactive_panes', False)
            self.enabled    = Prefs().get('fade_inactive_panes', False)
            self.grey_scale = Prefs().get('fade_inactive_panes_grey_scale', .2)

            # Reset panes
            self.reset(disable)

    def cycling_reset(self):
        """Retry accessing the active window until it is available
        """
        if not sublime.active_window():
            sublime.set_timeout(lambda: self.cycling_reset, 50)
        else:
            self.reset()

    def reset(self, disable=False):
        """Delete temporaryly generated dimmed files.
        """
        # "Disable" the plugin first (as in, remove all references to dimmed schemes).
        self.refresh_views(True)

        # Delete all subdirs of this module.
        for root, dirs, files in os.walk(module_path):
            if '.git' in dirs:
                dirs.remove('.git')  # do not iterate over .git or subdirs
            for di in dirs:
                shutil.rmtree(os.path.join(root, di))

        if not disable:
            self.refresh_views()

    def refresh_views(self, disable=False):
        active_view_id = sublime.active_window().active_view().id()
        for window in sublime.windows():
            for v in window.views():
                if v.settings().get('is_widget'):
                    continue

                if disable or v.id() == active_view_id:
                    self.on_activated(v)
                else:
                    self.on_deactivated(v)

    def create_inactive_scheme(self, scheme):
        """This is where the fun begins.
        """
        # Unfortunately, scheme paths start with "Packages/" and packages_path ends with
        # "Packages/", so we add a .. in the middle when we combine them.
        # TOCHECK: do absolute paths work?
        source_abs = os.path.normpath(os.path.join(sublime.packages_path(), "..", scheme))

        # `commonprefix()` isn't guaranteed to return a complete path, so we take the dirname to
        # get something real. All that really matters is that the path points unambiguously to one
        # color scheme, though we'd prefer for it to be as short as possible.
        #
        # TOCHECK: "Package/Inactive..." as path for scheme
        prefix = os.path.dirname(os.path.commonprefix([source_abs, module_path]))
        # `prefix` will most likely be the packages path.
        source_rel = os.path.relpath(source_abs, prefix)

        # Reconstruct the relative path inside of our module directory--we
        # have something of a shadow copy of the scheme.
        dest = os.path.join(module_path, source_rel)

        # Copy and dim the scheme if it does not exist
        if not os.path.isfile(dest):
            destdir = os.path.dirname(dest)
            if not os.path.isdir(destdir):
                os.makedirs(destdir)

            if ST2:
                shutil.copy(source_abs, dest)
            else:
                # ST3 does not unzip .sublime-packages, thus the `load_resource` API will be used.
                with open(dest, 'w') as f:
                    f.write(sublime.load_resource(scheme))

            self.dim_scheme(dest)

        # Sublime Text only likes relative paths for its color schemes.
        return os.path.join("Packages", module_name, source_rel).replace("\\", "/")

    def dim_scheme(self, scheme):
        print("[InactivePanes] Generating dimmed color scheme for '%s'" % scheme)
        print("[InactivePanes] Grey scale: %s" % self.grey_scale)

        def dim_rgb(match):
            rgb = list(match.groups())
            orig_scale = 1 - self.grey_scale
            # Average toward grey
            for i, c in enumerate(rgb):
                rgb[i] = int(int(c, 16) * orig_scale + 127 * self.grey_scale)

            return "#{0:02x}{1:02x}{2:02x}".format(*rgb)

        with open(scheme) as f:
            text = f.read()

        text = re.sub("#" + (r"([0-9a-fA-F]{2})" * 3), dim_rgb, text)
        with open(scheme, 'w') as f:
            f.write(text)

    # The actual event handlers
    def on_activated(self, view):
        vsettings = view.settings()
        if view is None or vsettings.get('is_widget'):
            return
        # Get the previous theme of the current view, defaulting to the default setting
        # (if this was ever to happen).
        default_scheme = vsettings.get('default_scheme', Prefs().get('color_scheme'))
        if default_scheme:
            vsettings.set('color_scheme', default_scheme)
            vsettings.erase('default_scheme')
        elif self.enabled:
            vsettings.erase('color_scheme')

    def on_deactivated(self, view):
        if view is None or view.settings().get('is_widget'):
            return

        if not Prefs().get('fade_inactive_panes', False):
            return

        # Reset to the base color scheme first if there was any
        # (I don't know anymore why this is necessary).
        self.on_activated(view)

        # Note: all "scheme" paths here are relative
        active_scheme = view.settings().get('color_scheme')
        view.settings().erase('color_scheme')
        default_scheme = view.settings().get('color_scheme')
        if active_scheme != default_scheme:
            # Because the settings do not equal after removing the view-specific setting
            # the view's color scheme is expicitly set so save it for later.
            view.settings().set('default_scheme', active_scheme)

        # Potentially copy and dim the scheme
        inactive_scheme = self.create_inactive_scheme(active_scheme)

        view.settings().set('color_scheme', inactive_scheme)


# Use this local instance for all the references
inpanes = InactivePanes()


class InactivePaneCommand(sublime_plugin.EventListener):
    delay = 150

    def on_activated(self, view):
        if view is None or view.settings().get('is_widget'):
            return
        sublime.set_timeout(lambda: inpanes.on_activated(view), self.delay)

    def on_deactivated(self, view):
        if view is None or view.settings().get('is_widget'):
            return
        sublime.set_timeout(lambda: inpanes.on_deactivated(view), self.delay)


def plugin_loaded():
    # "Initialize" the instance here
    inpanes.init()


def plugin_unloaded():
    print("unloading")
    inpanes.reset(True)
    print("unloaded")

# ST2 backwards (and don't call it twice in ST3)
unload_handler = plugin_unloaded if ST2 else lambda: None

if ST2:
    plugin_loaded()
