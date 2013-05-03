Inactive Panes
==============

Inactive Panes is a plugin for [Sublime Text][st] that will dim (or gray) the currently inactivate panes to show you more visibly where your cursor is at and which view is focussed. Really Useful with the [Origami][origami] plugin or ST3's native panel handling.

**Warning**: Do not use this with other color-changing plugins like [LiveCSS][livecss] as it will probably cause various issues and eventually *bring the world to an end*.


About
-----

Inactive Panes is a split from [Origami][origami] which once included this feature but due to various (unfixable) issues it was removed. I extracted relevant commits from the Origami repo to keep developing this feature because I've used it ever since (with no issues yet) and think that it's really useful.


Originally created by [adzenith][adzenith], maintained by [FichteFoll][FichteFoll].


Install
-------

This plugin is not yet available through Package Control since it is still in early development, you have to install it manually by browsing the [Packages][packages-dir] sub-folder of your [Data directory][data-dir] and cloning the repo.

    git clone git://github.com/SublimeText/InactivePanes.git

Alternatively you can download a [zip archive][zip] and extract it into an "Inactive Panes" sub-directory of the Packages dir mentioned above.


[st]: https://www.sublimetext.com/
[origami]: https://github.com/SublimeText/Origami
[livecss]: https://github.com/a-sk/livecss

[adzenith]: https://github.com/adzenith
[FichteFoll]: https://github.com/FichteFoll

[data-dir]: http://docs.sublimetext.info/en/latest/basic_concepts.html#the-data-directory
[packages-dir]: http://docs.sublimetext.info/en/latest/basic_concepts.html#the-packages-directory
[zip]: https://github.com/SublimeText/InactivePanes/zipball/master
