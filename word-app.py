import sqlite3
import textwrap
import json
from datetime import date, timedelta
import random

sqliteConnection = sqlite3.connect('words.db')

####################################################################################################

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

####################################################################################################

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
  user_input = input("Enter word tags separated by ',' (optional): ")
  comma_separated_input = user_input.split(',')
  stripped_input = list(map(lambda x: x.strip(), comma_separated_input))
  filtered_out_input = list(filter(lambda x: len(x) > 0, stripped_input))
  return filtered_out_input

def _persist_new_word(new_word, new_word_translation, new_word_example_use, new_word_tags):
  create_new_word_query = f"""
    INSERT INTO words (word, word_translation, example_use, tags, next_ask_date, ask_results) VALUES
    (?, ?, ?, ?, date(), '[]');
  """
  cursor = sqliteConnection.cursor()
  cursor.execute(
    create_new_word_query,
    (new_word, new_word_translation, new_word_example_use, ",".join(new_word_tags).replace("'", "''"))
  )
  sqliteConnection.commit()
  cursor.close()

def start_add_word_state_machine():
  while(True):
    print("Add new word pannel. Follow instructions:")
    new_word = _get_word()
    new_word_translation = _get_word_translation()
    new_word_example_use = _get_example_use()
    new_word_tags = _get_tags()
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
        _persist_new_word(new_word, new_word_translation, new_word_example_use, new_word_tags)
        print("Word has been added")
        return
      elif user_input == "n":
        print("Incorect word data... Try once again.")
        break
      else:
        print("Unknown command. Try again one more time.")


####################################################################################################

def _get_words_to_ask():
  cursor = sqliteConnection.cursor()
  select_for_words_query = """
    SELECT id, word, word_translation, example_use, tags, next_ask_date, ask_results
    FROM words
    WHERE next_ask_date <= date()
    LIMIT 100;
  """
  cursor.execute(select_for_words_query)
  rows = cursor.fetchall()
  cursor.close()
  random.shuffle(rows)
  selected_rows = rows[:20]
  return list(map(lambda x: {'id': x[0], 'word': x[1], 'word_translation': x[2], 'example_use': x[3], 'tags': x[4], 'next_ask_date': x[5], 'ask_results': json.loads(x[6])}, selected_rows))

def _calculate_next_ask_date(word):
  if not word['ask_results'][-1]['correct']:
    return date.today().strftime("%Y-%m-%d")
  score = len(list(filter(lambda x: x, map(lambda x: x['correct'], word['ask_results'][-5:]))))
  return {
    0: date.today(),
    1: date.today() + timedelta(days=1),
    2: date.today() + timedelta(days=3),
    3: date.today() + timedelta(days=5),
    4: date.today() + timedelta(days=10),
    5: date.today() + timedelta(days=15)
  }.get(score).strftime("%Y-%m-%d")

def _save_word(word):
  cursor = sqliteConnection.cursor()
  update_words_query = """
    UPDATE words
    SET word=?, word_translation=?, example_use=?, tags=?, next_ask_date=?, ask_results=?
    WHERE id = ?;
  """
  cursor.execute(update_words_query, (word['word'], word['word_translation'], word['example_use'], word['tags'], word['next_ask_date'], json.dumps(word['ask_results']), word['id']))
  sqliteConnection.commit()
  cursor.close()

def _mark_as_correct(word, words_to_ask):
  if not word.get('alredy_answered', False):
    word['ask_results'].append({'correct': True, 'asked_at': date.today().strftime("%Y-%m-%d")})
    word['next_ask_date'] = _calculate_next_ask_date(word)
    _save_word(word)

def _mark_as_incorrect(word, words_to_ask):
  if not word.get('alredy_answered', False):
    word['ask_results'].append({'correct': False, 'asked_at': date.today().strftime("%Y-%m-%d")})
    word['next_ask_date'] = _calculate_next_ask_date(word)
    _save_word(word)
  word['alredy_answered'] = True
  words_to_ask.append(word)

def start_practice_words_state_machine():
  print("Practice word pannel.")
  words_to_ask = _get_words_to_ask()
  if len(words_to_ask) == 0:
    print("No words to ask; try again tommorow.")
    return
  while len(words_to_ask) > 0:
    word = words_to_ask.pop(0)
    print("Word translation: " + word['word_translation'])
    print("Tags: " + str(word['tags']))
    input("Press 'Enter' any button to show answer")
    print("Word: " + word['word'])
    print("Example use: " + word['example_use'])
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
  print("Finishing practise word session.")

####################################################################################################

def start_main_state_machine():
  while(True):
    print("Main pannel. What do you want to do?")
    user_input = input("Actions: 'e' -> exit, 'a' -> add new word, 'p' -> pratcise words: ")
    if user_input == "e":
      print("Exiting program. Bye!")
      return
    elif user_input == "a":
      start_add_word_state_machine()
    elif user_input == "p":
      start_practice_words_state_machine()
    else:
      print("Unknown command. Try again one more time.")

migrate_database()
start_main_state_machine()