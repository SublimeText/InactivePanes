# InactivePanes

InactivePanes is a plugin for [Sublime Text][st] 2 and 3 that will dim the
currently visible but inactivate panes to show you more visibly where your
caret is and which view is focussed. Really useful with the [Origami][]
plugin or ST3's native panel handling.

This plugin could have incompatabilities with other plugins that modify color
schemes programmatically, but so far no issues have been found. Please report
errors you *do* encounter with this plugin [here][issues], also if they are not
related to other plugins.

Originally created by [adzenith][], maintained by
[FichteFoll][].

### Installation

You can install this package from [Package Control][] as
"InactivePanes".


## Usage

Views in inactive groups will automatically dimmed automatically when you
install it.

When you want to disable this package, use Package Control's *Disable Package*
and *Enable Package* commands. Alternatively you can adjust your
`"ignored_packages"` setting manually.

**Warning**: If you want to remove the package, use Package Control's *Remove
Package* command. Do **not** delete the plugin folder by yourself if you didn't
disable the package before and ST is not running! This will cause various error
messages because of outdated file references (but nothing critical).

### Configuration

The following settings can be specified everywhere where you'd specify a
`color_scheme` - user settings (*Preferences &gt; Settings - User*),
syntax-specific (*Preferences &gt; Settings - More &gt; Syntax Specific - User*)
or [project settings][projset]. Thus, you can adjust each color scheme
separately to blend with your theme's sidebar for example.

*   `"inactive_panes_dim_color"` (*default*: `"#7F7F7F"`, gray)

    Change the color to dim to. Must be in the format `#RRGGBB` with hexadecimal
    numbers.

*   `"inactive_panes_dim_strength"` (*default*: `0.2`)

    Change the dim strength; ranges from `0` (no modification) to `1`
    (everything will be changed to the color set above).

### Images

#### Dark Scheme

Using [a modified][tw-fichte] Twilight color scheme with a dim strength of
`0.1`:

[![][scr-dark-thumb]][scr-dark]

#### Bright Scheme

Using the bundled LAZY color scheme with a dim strength of `0.3`:

[![][scr-bright-thumb]][scr-bright]

#### Custom Color

Using [a modified][tw-fichte] Twilight color scheme with a custom color of
`"#7F7F00"` and dim strength of `0.1`:

[![][scr-dark_colored-thumb]][scr-dark_colored]


### Known Issues

- When opening the same file in two groups (with command palette or by cloning
  it), both of the views will be marked as inactive. This is caused by an
  underlying Sublime Text bug
  (https://github.com/SublimeTextIssues/Core/issues/731) and can be worked
  around by **restarting Sublime Text** after cloning.


## About

InactivePanes is a split from [Origami][origami] which once included this
feature but due to various issues it was removed. I extracted relevant commits
(for retaining the commit history) from the Origami repo to keep developing
this feature because I've used it ever since and think that it's really useful.


<!-- General links -->
[st]: https://www.sublimetext.com/
[Origami]: https://github.com/SublimeText/Origami
[issues]: https://github.com/SublimeText/InactivePanes/issues
[adzenith]: https://github.com/adzenith
[FichteFoll]: https://github.com/FichteFoll

<!-- Themes and Images -->
[tw-fichte]: https://gist.github.com/FichteFoll/5522507 "Gist: Twilight-Fichte.tmTheme"
[scr-dark]: http://i.imgur.com/4uKGLf3.png "Twilight color scheme; 0.1"
[scr-dark-thumb]: http://i.imgur.com/4uKGLf3l.png
[scr-bright]: http://i.imgur.com/CCcl1v3.png "LAZY color scheme; 0.3"
[scr-bright-thumb]: http://i.imgur.com/CCcl1v3l.png
[scr-dark_colored]: http://i.imgur.com/m5rc8j9.png "Twilight color scheme; 0.08; #7F7F00"
[scr-dark_colored-thumb]: http://i.imgur.com/m5rc8j9l.png

<!-- Specific (documentation) links -->
[projset]: http://www.sublimetext.com/docs/3/projects.html "Projects"
[Package Control]: https://packagecontrol.io/ "Package Control"
