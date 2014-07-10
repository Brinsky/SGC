"""This is the Steam Game Comparator (SGC), it finds the overlap between
   the game collections of multiple Steam users."""

import sys
import httplib2
import json
from bs4 import BeautifulSoup


class MultipleProfileHits(Exception):
    pass


class PrivateProfile(Exception):
    pass


class MissingProfile(Exception):
    pass


# The master games dictionary which will contain ever game owned by any
# player. The dictionary also associates appids with game titles, allowing
# game lists for players to contain only appids.
master_games = {}


MAX_PLAYERS = 10
NAME_LENGTH = 8
TITLE_LENGTH = 25


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

 
def get_player_games(partial_url):
    """Get a set containing the names of every game owned by a player on Steam

    Requires the player username or custom URL segment used in that player's
    community URL. Example: ...steamcommunity.com/profiles/commun_name/..."""

    # A list of dictionaries containing information about possible Steam
    # URLs. The status element is used to track whether the profile has been
    # succesfully accesed, is private, or does not exist.
    possible_urls = [
          { 'url': "http://steamcommunity.com/profiles/" + partial_url +
            "/games/?tab=all", 'status': None },
          { 'url': "http://steamcommunity.com/id/" + partial_url +
            "/games/?tab=all", 'status': None } ]

    num_exist = 0

    for url_dict in possible_urls:
        content = get_html(httplib2.Http(), url_dict['url'])
        soup = BeautifulSoup(content)

        # If the profile/gameslist is accessed properlu
        if soup.find('div', class_='games_list'):
            url_dict['status'] = 'success'
            num_exist += 1

            # What if more than one URL combo works? It shouldn't, throw an exception!
            if num_exist > 1:
                raise MultipleProfileHits( str(num_exist) +
                    " profile/game pages found for the same URL segment. " +
                    "What the HAY?!?!")

            # An exception will be thrown if more than one url is succesful
            # so we might as well grab the content from any successful case
            content_str = soup.prettify()

        # If the profile is private
        elif soup.find('div', class_='profile_private_info'):
            url_dict['status'] = 'private'
            num_exist += 1

            # What if more than one URL combo works? It shouldn't, throw an exception!
            if num_exist > 1:
                raise MultipleProfileHits( str(num_exist) +
                    " profile/game pages found for the same URL segment. " +
                    "What the HAY?!?!")

            raise PrivateProfile("User profile is private.")


    if num_exist == 0:
        raise MissingProfile("User profile is missing.")

    # Get a substring containing the definition of "var rgGames"
    js_str = content_str[ content_str.index("rgGames") : ]
    js_str = js_str[ js_str.index("[") : (js_str.index("]") + 1) ]

    # Convert that value to a valid python list
    js_value = json.loads(js_str)

    # Store all of the game appids for a player within a set
    player_games = set()
    for d in js_value:
        player_games.add(d['appid'])
        # Also add the appids to the master dictionary, along with their names
        master_games[ d['appid'] ] = d['name']

    return player_games


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


def handle_input_str(msg, min, max):
    """Repeats a request until the user inputs a string within a given
    length."""

    while True:
        val = input(msg)

        if len(val) < min:
           print("String too short! Minimum is " + str(min) +
                 " characters. Try again.")
           continue
        elif len(val) > max:
           print("String too long! Limit is " + str(max) + 
                 " characters. Try again")
           continue

        break;

    return val


def is_yes(in_val):
    """Tests if the first character of a string == 'Y'"""

    if in_val[:1] == 'Y':
        return True
    else:
        return False


def make_length(string, length):
    """Forces a string to be a certain length by either cutting or
    padding it"""

    if len(string) > length:
        return string[:length-3] + "..."
    else:
        return string + ( (length - len(string)) * ' ')

def create_chart(shared_games, player_data):
    """Outputs a chart indicating which games are shared among which
    players"""

    names_out = make_length("Game Title", TITLE_LENGTH) + ' +'
    separator_out = ('-' * (TITLE_LENGTH + 1)) + '+'

    for player in player_data:
        names_out += '  '
        names_out += make_length(player['nick'], NAME_LENGTH)
        names_out += ' +'
        separator_out += ('-' * (NAME_LENGTH + 3)) + '+'

    print(names_out)
    print(separator_out)

    for appid in shared_games:

        game_out = make_length( master_games[appid], TITLE_LENGTH ) + ' |'
        for player in shared_games[appid]:
            game_out += ' ' * 5
            if player == True:
                game_out += 'X'
            else:
                game_out += ' '
            game_out += (' ' * 5) + '|'

        print(game_out)

    print(separator_out)

    print("Fun fact: This group of players owns a total of " +
        str(len(master_games)) + " unique games!")


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


def attempt_skip(num_players, skipped, msg):
    """Checks whether it is possible to skip over a player and continue
    running the program. Fails if 1 or fewer players would remain."""

    print(msg)

    if skipped >= num_players - 2:
        print("Not enough players left to continue. Exiting...")
        return False
    else:
        return  is_yes(input(" Skip this player? (Y/N, N exits): ")[:1])
        

def find_player_data(num_players):
    """Create a list to track players and their data. The end result will be a
    list of dictionaries. The dictionaries will contain the player's name and
    a set containing the appids of all games owned by the player."""

    player_data = []
    skipped = 0

    # Gather all the data for each player and handle exceptions
    for i in range(0,num_players):
        nick = handle_input_str("Provide a nickname for player " +
            str(i+1) + " (under 9 characters): ", 1, NAME_LENGTH)

        # Don't repeat the long instructions, they take up too much space
        if i == 0:
            url_chunk = handle_input_str(
                "Enter the Steam Community URL segment for " + nick +
                "\n(The starred value from either" +
                "'http://steamcommunity.com/profiles/*****/' or" +
                "'http://steamcommunity.com/id/*****/'): ", 1, 100)
        else:
            url_chunk = handle_input_str(
                "Enter the Steam Community URL segment for " + nick +
                ": ", 1, 100)

        try:
            games = get_player_games(url_chunk)
        except PrivateProfile:
            # Skip the profile or exit if the profile is private
            if attempt_skip(num_players, skipped, "The profile for " + nick +
                " is private."):

                skipped += 1
                continue
            else:
                sys.exit()
        except MissingProfile:	
            # Skip the profile or exit if the profile is missing
            if attempt_skip(num_players, skipped, "The profile for " + nick +
                " cannot be found (not public or private). Maybe the URL was" +
                " wrong."):

                skipped += 1
                continue
            else:
                sys.exit()

        player_data.append( {'nick': nick, 'games': games } )
        print("Fun fact: " + nick + ' owns ' + str(len(games)) + ' games!')

    return player_data


def main():

    print("Welcome to the Steam Game Comparator!")

    num_players = handle_input_int("Number of accounts to compare? (2-10): ",
        2, MAX_PLAYERS)

    # Acquire data on the players
    player_data = find_player_data(num_players)

    # Determine which games are shared
    shared_games = find_common_games(player_data)

    if shared_games != None:
        # Maybe sort shared_games here?

        # Format and print out the results
        create_chart(shared_games, player_data)
    else:
        print("No games in common, despite owning " + len(master_games) +
            "games!")


if __name__ == '__main__':
    main()
