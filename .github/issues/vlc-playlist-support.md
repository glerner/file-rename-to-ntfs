# Add Support for Updating VLC Media Player Playlists

## Description
Add functionality to update VLC Media Player playlist files (`.m3u`) when renaming files. This ensures that playlists remain functional after files are renamed to be NTFS-compatible.

## VLC Playlist Format
VLC playlists use the `.m3u` format with two lines per entry:
1. An `#EXTINF` line containing duration and display name
2. A URL-encoded file path

Example:
```
#EXTINF:3350,Example Video Title.mp4
file:///home/user/Videos/Example%20Video%20Title.mp4
```

## Requirements
- [ ] Add option to specify input playlist file(s)
- [ ] Parse `.m3u` playlist format
- [ ] Handle both parts of each entry:
  - [ ] Update the display name after the comma in `#EXTINF` line
  - [ ] Update the URL-encoded file path to match renamed file
- [ ] Preserve duration and other metadata
- [ ] Handle URL encoding/decoding correctly
- [ ] Create backup of original playlist file
- [ ] Add tests with sample playlist entries

## Example Transformation
Original playlist entry:
```
#EXTINF:3350,Eben Pagan Metamind Creating Immersive Experiences with A.I. & Design (The Future of Media Design!).mp4
file:///home/george/Videos/Eben%20Pagan%20Metamind%20Creating%20Immersive%20Experiences%20with%20A.I.%20%26%20Design%20%28The%20Future%20of%20Media%20Design%21%29.mp4
```

After file rename:
```
#EXTINF:3350,Eben Pagan Metamind Creating Immersive Experiences with AI and Design ⦃The Future of Media Design⦄.mp4
file:///home/george/Videos/Eben%20Pagan%20Metamind%20Creating%20Immersive%20Experiences%20with%20AI%20and%20Design%20%E2%A6%83The%20Future%20of%20Media%20Design%E2%A6%84.mp4
```
Note that the video is 55 minutes 50 seconds long; 55×60+50=3350 seconds.
## Technical Notes
- Need to handle both the display text and URL-encoded versions of filenames
- Special characters in new filenames (like ⦃⦄) need proper URL encoding
- Consider using Python's `urllib.parse` for URL encoding/decoding
- May need to detect playlist encoding (usually UTF-8)

## Related
- Main file renaming functionality in `file_renamer.py`
- Special character replacement mappings
