# Import station collections from a URL

FluxTuner supports importing M3U, M3U8 and PLS station collections
from an HTTP or HTTPS URL, without downloading the file manually.

## GTK

Open the application menu and select **Import stations from URL…**.
Enter the collection URL, preview its stations and choose a destination
playlist before confirming the import.

## TUI

Open the station import screen and enter either a local file path or
an HTTP/HTTPS collection URL. Preview the collection and confirm the
destination playlist to save the stations.

## Web

Open **Import stations…** and enter a collection URL or select a local
file. Preview the stations and choose a destination before importing.

## Safety and limits

- Remote collections are limited to 1 MiB.
- HTTP redirects and destination addresses are subject to network
  security checks, including restrictions on private addresses.
- Importing requires an explicit confirmation.
- The preview and confirmation use the same downloaded collection;
  saving does not fetch the remote URL again.
- Existing favorite names and tags are preserved.
- Importing does not connect to the individual radio streams.

Remote subscriptions, automatic updates and authenticated collection
sources are not supported by this feature.
