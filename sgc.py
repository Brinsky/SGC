"""This is the Steam Game Comparator (SGC), it finds the overlap between
   the game collections of multiple Steam users."""

# Third-party/external imports
import httplib2
from bs4 import BeautifulSoup

import sys
import json
import time
import datetime


class PrivateProfile(Exception):
    pass

class MissingProfile(Exception):
    pass

class MalformedSteamURL(Exception):
    pass

class FindNameError(Exception):
    pass

class FindGamesError(Exception):
    pass


# The master games dictionary which will contain ever game owned by any
# player. The dictionary also associates appids with game titles, allowing
# game lists for players to contain only appids.
master_games = {}

MAX_PLAYERS = 10
NAME_LENGTH = 8
TITLE_LENGTH = 25
FILE_PATH = "output/"


def get_html(h, url):
    """Gets an HTML file from a URL.

    Requires an httplib2.Http object and a string URL
    """

    # Request and verify data from URL
    resp, content = h.request(url)
    assert resp.status == 200
    assert 'text/html' in resp['content-type']

    # Return HTML document as bytes
    return content


def get_player_and_games(url):
    """Attempts to access Steam Community data and determine a player's name
    and games list. This attempt is made using the URL of the player's profile
    page."""

    # Navigate to profile's games page
    url += '/games/?tab=all'

    content = get_html(httplib2.Http(), url)
    soup = BeautifulSoup(content)

    # If the profile/gameslist is accessed properlu
    if soup.find('div', class_='games_list'):
        # Convert HTML contents into a string for further parsing
        content_str = soup.prettify()

        # Get a substring containing the JS definition of 'var personaName'
        try:
            js_name = content_str[ content_str.index("personaName"): ]
            js_name = js_name[ js_name.index('"'):js_name.index(';') ]
        except ValueError:
            raise FindNameError()
        name = json.loads(js_name)

        # Get a substring containing the JS definition of 'var rgGames'
        try:
            js_str = content_str[ content_str.index("rgGames") : ]
            js_str = js_str[ js_str.index("[") : (js_str.index("]") + 1) ]
        except ValueError:
            raise FindGamesError()
        js_value = json.loads(js_str)

        # Store all of the game appids for a player within a set
        player_games = set()
        for d in js_value:
            player_games.add(d['appid'])
            # Also add the appids to the master dictionary, along with their names
            master_games[ d['appid'] ] = d['name']

        # Return the player's Steam name and games dictionary
        return (name, player_games)

    # If the profile is private
    elif soup.find('div', class_='profile_private_info'):
        raise PrivateProfile()

    else:
        raise MissingProfile()


def handle_input_int(msg, min, max):
    """Repeats a request until the user inputs an integer within a given
    range."""

    while True:
        try:
           val = int(input(msg))
        except ValueError:
           print("Invalid input! Try again.")
           continue

        if val not in range(min,max+1):
           print("Number not in range! Try again.")
           continue

        break;

    return val


def make_length(string, length):
    """Forces a string to be a certain length by either cutting or
    padding it"""

    if len(string) > length:
        return string[:length-3] + "..."
    else:
        return string + ( (length - len(string)) * ' ')


def get_formatted_time():
    """Returns a timestamp formatted to be a filename-friendly string"""

    return datetime.datetime.fromtimestamp(time.time()).strftime(
        '%Y-%m-%d_%H-%M-%S')


def create_chart(shared_games, player_data):
    """Outputs a chart indicating which games are shared among which
    players. Returns the name of the chart file."""

    file_name = get_formatted_time() + '.txt'
    f = open(FILE_PATH + file_name, 'w')

    names_out = make_length("Game Title", TITLE_LENGTH) + ' +'
    separator_out = ('-' * (TITLE_LENGTH + 1)) + '+'
    blank_out = (' ' * (TITLE_LENGTH + 1)) + '|'
    
    for player in player_data:
        names_out += '  '
        names_out += make_length(player['nick'], NAME_LENGTH)
        names_out += ' +'
        separator_out += ('-' * (NAME_LENGTH + 3)) + '+'
        blank_out += (' ' * (NAME_LENGTH + 3)) + '|'

    print(names_out, file=f)
    print(separator_out, file=f)

    for appid in shared_games:

        game_out = make_length( master_games[appid], TITLE_LENGTH ) + ' |'
        for player in shared_games[appid]:
            game_out += ' ' * 5
            if player == True:
                game_out += 'X'
            else:
                game_out += ' '
            game_out += (' ' * 5) + '|'

        print(blank_out, file=f)
        print(game_out, file=f)
        print(blank_out, file=f)

    print(separator_out, file=f)

    # Bonus fun facts section
    print("Fun facts:", file=f)

    for player in player_data:
        print(player['nick'] + " owns " + str(len(player['games'])) +
            " total games.", file=f)

    print("This group of players owns a total of " +
        str(len(master_games)) + " unique games!", file=f)

    f.close()
    return file_name


def find_common_games(player_data):
    """Returns a dictionary containing the appids of shared games
    and a list indicating which users own each game."""

    shared_games = {}

    for appid in master_games:

        # List (in the same order as the player list) indicating who owns
        # the current game
        current_game = []

        total_owners = 0

        for player in player_data:
            if appid in player['games']:
                current_game.append(True)
                total_owners += 1
            else:
                current_game.append(False)

        # If more than one player owns the game, place it into the shared
        # dictionary along with a list of which players own it
        if total_owners > 1:
            shared_games[appid] = current_game

    if len(shared_games) == 0:
        return None

    return shared_games


def verify_steam_url_format(url):
    """Verifies that a given URL is a valid  Steam Community profile URL.
    If the URL has trailing information, it attempts to truncate it.

    NOTE: This method does not actually check if the profiles exist, nor
    does it check for invalid characters in the URL."""

    # All possible input types that are accepted
    formats = [ 'http://steamcommunity.com/profiles/',
        'http://steamcommunity.com/id/',
        'steamcommunity.com/profiles/',
        'steamcommunity.com/id/' ]

    # Does the given URL match any accepted formats?
    for possible in formats:
        # If the formats are found, they should be found at index 0
        if url.find(possible) == 0:
            # Find any extra slashes in the URL so that they can be removed
            trailing_slash = url.find('/', len(possible))
            break
    else:
        raise MalformedSteamURL()

    # If it existed, truncate that extra / and anything following it
    # Do this FIRST, it depends on an index that needs to stay accurate
    if trailing_slash >= 0:
        url = url[:trailing_slash]

    # If it doesn't have the 'http://', it needs it
    if url.find('http://') == -1:
        url = 'http://' + url

    return url


def find_player_data():
    """Create a list to track players and their data. The end result will be a
    list of dictionaries. The dictionaries will contain the player's name and
    a set containing the appids of all games owned by the player."""

    player_data = []

    print("Enter the URLs of each Steam profile to be compared.")
    print("(ex. 'http://steamcommunity.com/id/profilename' or " +
        "'http://steamcommunity.com/profile/829839292863872')")
    print("Return an empty field when finished.")

    while True:
        url = input('URL #' + str(len(player_data) + 1) + ': ')

        # The user enters nothing, indicating that they are finished
        if not url:
            # We need to have two or more valid players to compare
            if len(player_data) > 1:
                break
            else:
                print("ERROR: Two or more players are required for comparison.")
                continue

        # Validate URL formatting
        try:
            url = verify_steam_url_format(url)
        except MalformedSteamURL:
            print("ERROR: URL format not valid/recognized!")
            continue

        # Validate profile and retrieve games
        try:
            name, games = get_player_and_games(url)
        except PrivateProfile:
            print("ERROR: Profile appears to be private.")
            continue
        except MissingProfile:
            print("ERROR: Profile not found (neither public nor private) or not recognized.")
            continue
        except FindNameError:
            print("ERROR: Could not retrieve player's name.")
            continue
        except FindGamesError:
            print("ERROR: Could not retrieve player's games.")
            continue

        player_data.append( {'nick': name, 'games': games } )
        print('Successfully accessed profile for ' + name  + '.')

    return player_data


def main():

    print("Welcome to the Steam Game Comparator!")

    # Acquire data on the players
    player_data = find_player_data()

    # Determine which games are shared
    shared_games = find_common_games(player_data)

    if shared_games != None:
        # Maybe sort shared_games here?

        # Format and print out the results
        file_name = create_chart(shared_games, player_data)
        print("The comparision chart has been output to 'output/" + file_name +
            "'.")
    else:
        print("No games in common, despite owning " + len(master_games) +
            "games!")
        print("No chart created.")


if __name__ == '__main__':
    main()
