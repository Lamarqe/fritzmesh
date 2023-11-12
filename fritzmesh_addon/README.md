# Fritz Mesh
Home Assistant addon to include the Fritz!Box mesh overview in Home Assistant
<br/><br/>

![Screenshot](https://github.com/Lamarqe/fritzmesh/raw/main/fritzmesh_addon/screenshot.jpg)

Functionalities included:

 * Modify some css / js parameters to make the overview appear in fullscreen, irrespective of the available resolution
 * Mesh status is updated every 5 seconds

## Installation

 * navigate to `Configuration -> Addons, Backups & Supervisor -> Add-on Store`, select `Repositories` in the menu that appears when selecting the 3 dots on top right
 * Add `https://github.com/Lamarqe/fritzmesh` as a new repository
 * Afterwards, Fritz Mesh can be selected from the list of available Add-ons
 * Before starting first time, enter fritzbox access parameters.

## Configuration

Following configuration is required:
 * `Fritzbox username`: The username of your Fritz!Box. (Hint for being on the safe side: Create a new user without any permissions, just for the Add-on use-case)
 * `Fritzbox password`: Corresponding users password
 * `fritzbox host`: Hostname or IP under which the Fritz!Box is reachable (Default: fritz.box. This should work just fine for most setups)




