import sqlite3
import textwrap
import json
from datetime import date, datetime, timedelta
import random
import os

#################### DATABASE ####################

sqliteConnection = sqlite3.connect('words.db')

def migrate_database():
  create_words_table_if_not_exists_query = """
    CREATE TABLE IF NOT EXISTS words (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      word varchar(255),
      word_translation text,
      example_use text,
      tags varchar(255),
      next_ask_date varchar(64),
      ask_results text
    );
  """
  cursor = sqliteConnection.cursor()
  cursor.execute(create_words_table_if_not_exists_query)
  cursor.close()

def save_new_word(new_word):
  create_new_word_query = f"""
    INSERT INTO words (word, word_translation, example_use, tags, next_ask_date, ask_results) VALUES
    (?, ?, ?, ?, ?, ?);
  """
  cursor = sqliteConnection.cursor()
  cursor.execute(
    create_new_word_query,
    (new_word['word'], new_word['word_translation'], new_word['example_use'], ",".join(new_word['tags']), new_word['next_ask_date'], json.dumps(new_word['ask_results']))
  )
  sqliteConnection.commit()
  cursor.close()

def update_word(word):
  update_words_query = """
    UPDATE words
    SET word=?, word_translation=?, example_use=?, tags=?, next_ask_date=?, ask_results=?
    WHERE id = ?;
  """
  cursor = sqliteConnection.cursor()
  cursor.execute(update_words_query, (word['word'], word['word_translation'], word['example_use'], word['tags'], word['next_ask_date'], json.dumps(word['ask_results']), word['id']))
  sqliteConnection.commit()
  cursor.close()

def find_words(offset=0, limit=100):
  select_for_words_query = f"""
    SELECT id, word, word_translation, example_use, tags, next_ask_date, ask_results
    FROM words
    WHERE next_ask_date <= date()
    ORDER BY id desc
    LIMIT {offset},{limit};
  """
  cursor = sqliteConnection.cursor()
  cursor.execute(select_for_words_query)
  rows = cursor.fetchall()
  cursor.close()
  return list(map(lambda x: {'id': x[0], 'word': x[1], 'word_translation': x[2], 'example_use': x[3], 'tags': x[4], 'next_ask_date': x[5], 'ask_results': json.loads(x[6])}, rows))

##################### UTILS ######################

def clear_screen():
  os.system('clear')

#################### ADD WORD ####################

def _get_word():
  while(True):
    user_input = input("Enter new word: ").strip()
    if len(user_input) > 0:
      return user_input
    else:
      print("Word should have at least one letter")

def _get_word_translation():
  while(True):
    user_input = input("Enter new word translation: ").strip()
    if len(user_input) > 0:
      return user_input
    else:
      print("Word translation should have at least one letter")

def _get_example_use():
  user_input = input("Enter new word example use (optional): ").strip()
  return user_input

def _get_tags():
  while(True):
    user_input = input("Enter tag: 'w' -> word, 'p' -> phersalVerb, 'c' -> collocation: ")
    tag = {'w': 'word', 'p': 'phersalVerb', 'c': 'collocation'}.get(user_input, None)
    if tag is None:
      print("Tag accept one of values: 'w' -> word, 'p' -> phersalVerb, 'c' -> collocation")
      continue
    return [tag]

def start_add_word_state_machine():
  while(True):
    clear_screen()
    print("Add new word pannel. Follow instructions:")
    new_word = _get_word()
    new_word_translation = _get_word_translation()
    new_word_example_use = _get_example_use()
    new_word_tags = _get_tags()
    clear_screen()
    print("Add new word pannel.")
    print(textwrap.dedent(f"""\
      Does all data correct:
      word: {new_word}
      word translation: {new_word_translation}
      example use: {new_word_example_use}
      tags: {new_word_tags}"""
    ))
    while(True):
      user_input = input("Actions: 'y' -> data correct, 'n' -> data incorrect, 'e' -> exit to previous menu: ")
      if user_input == "e":
        print("Exiting from adding word pannel.")
        return
      elif user_input == "y":
        save_new_word({
          'word': new_word, 'word_translation': new_word_translation, 'example_use': new_word_example_use, 'tags': new_word_tags, 'next_ask_date': date.today(), 'ask_results': []
        })
        input("Word has been added. Press 'Enter' to continue...")
        return
      elif user_input == "n":
        print("Incorect word data... Try once again.")
        break
      else:
        print("Unknown command. Try again one more time.")

#################### ASK WORD ####################

def _get_words_to_ask():
  words = find_words(offset=0, limit=100)
  random.shuffle(words)
  return words[:20]

def _calculate_next_ask_date(word):
  if not word['ask_results'][-1]['correct']:
    return date.today().strftime("%Y-%m-%d")
  score = len(list(filter(lambda x: x, map(lambda x: x['correct'], word['ask_results'][-5:])))) - len(list(filter(lambda x: x, map(lambda x: not x['correct'], word['ask_results'][-5:]))))
  if score < 0:
    return date.today().strftime("%Y-%m-%d")
  return {
    0: date.today(),
    1: date.today() + timedelta(days=2),
    2: date.today() + timedelta(days=5),
    3: date.today() + timedelta(days=8),
    4: date.today() + timedelta(days=13),
    5: date.today() + timedelta(days=21)
  }.get(score).strftime("%Y-%m-%d")

def _mark_as_correct(word, words_to_ask):
  if not word.get('alredy_answered', False):
    word['ask_results'].append({'correct': True, 'asked_at': date.today().strftime("%Y-%m-%d")})
    word['next_ask_date'] = _calculate_next_ask_date(word)
    update_word(word)

def _mark_as_incorrect(word, words_to_ask):
  if not word.get('alredy_answered', False):
    word['ask_results'].append({'correct': False, 'asked_at': date.today().strftime("%Y-%m-%d")})
    word['next_ask_date'] = _calculate_next_ask_date(word)
    update_word(word)
  word['alredy_answered'] = True
  words_to_ask.append(word)

def start_practice_words_state_machine():
  words_to_ask = _get_words_to_ask()
  if len(words_to_ask) == 0:
    clear_screen()
    print("Practice word pannel.")
    print("No words to ask; try again tommorow.")
    input("Press 'Enter' to continue...")
    return
  while len(words_to_ask) > 0:
    word = words_to_ask.pop(0)
    clear_screen()
    print(textwrap.dedent(f"""\
      Practice word pannel.
      word translation: {word['word_translation']}
      tags: {str(word['tags'])}
      word: **********
      example use: **********"""
    ))
    input("Press 'Enter' to show answer...")
    clear_screen()
    print(textwrap.dedent(f"""\
      Practice word pannel.
      word translation: {word['word_translation']}
      tags: {str(word['tags'])}
      word: {word['word']}
      example use: {word['example_use']}"""
    ))
    while True:
      user_input = input("Actions: 'y' -> correct answer, 'n' -> incorrect answer, 'e' -> exit session: ")
      if user_input == "e":
        print("Finishing practise word session.")
        return
      elif user_input == "y":
        _mark_as_correct(word, words_to_ask)
        break
      elif user_input == "n":
        _mark_as_incorrect(word, words_to_ask)
        break
      else:
        print("Unknown command. Try again one more time.")
  clear_screen()
  print("Practice word pannel.")
  print("Practice session finished.")
  input("Press 'Enter' to continue...")

################## MAIN PROGRAM ##################

def start_main_state_machine():
  shoud_clean_screen = True
  while(True):
    if shoud_clean_screen:
      clear_screen()
      shoud_clean_screen = False
    print("Main pannel. What do you want to do?")
    user_input = input("Actions: 'e' -> exit, 'a' -> add new word, 'p' -> pratcise words: ")
    if user_input == "e":
      print("Exiting program. Bye!")
      return
    elif user_input == "a":
      start_add_word_state_machine()
      shoud_clean_screen = True
    elif user_input == "p":
      start_practice_words_state_machine()
      shoud_clean_screen = True
    else:
      print("Unknown command. Try again one more time.")

###################### MAIN ######################

migrate_database()
start_main_state_machine()