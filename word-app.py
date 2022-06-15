import sqlite3
import textwrap
import json
from datetime import date, timedelta
import random
import os
from enum import Enum
import re

#################### DATABASE ####################

class FindWordsBuilder:
  def __init__(self, connection):
    self.connection = connection
    self.offset = 0
    self.limit = 10
    self.id_is = None
    self.id_is_not = None
    self.word_is = None
    self.word_like = None
    self.ask_date_is_due = False
    self.order_by_ask_date_asc = False
  
  def with_offset(self, offset):
    self.offset = offset
    return self

  def with_limit(self, limit):
    self.limit = limit
    return self
  
  def where_id_is(self, id_is):
    self.id_is = id_is
    return self
  
  def where_id_is_not(self, id_is):
    self.id_is = id_is
    return self

  def where_word_is(self, word_is):
    self.word_is = word_is
    return self
  
  def where_word_like(self, word_like):
    self.word_like = '%' + word_like + '%'
    return self

  def where_ask_date_is_due(self):
    self.ask_date_is_due = True
    return self
  
  def order_by_ask_date(self):
    self.order_by_ask_date_asc = True
    return self

  def find(self):
    select_for_words_query = f"""
      SELECT id, word, word_translation, example_use, tags, next_ask_date, ask_results
      FROM words
      WHERE 1=1
      {"AND id = ?" if self.id_is is not None else ""}
      {"AND id <> ?" if self.id_is_not is not None else ""}
      {"AND word = ?" if self.word_is is not None else ""}
      {"AND word like ?" if self.word_like is not None else ""}
      {"AND next_ask_date <= date()" if self.ask_date_is_due else ""}
      ORDER BY {"next_ask_date asc, " if self.order_by_ask_date_asc else ""} id asc
      LIMIT ?,?;
    """
    cursor = self.connection.cursor()
    cursor.execute(select_for_words_query, tuple(x for x in (self.id_is, self.id_is_not, self.word_is, self.word_like, self.offset, self.limit) if x is not None))
    rows = cursor.fetchall()
    cursor.close()
    return list(map(lambda x: {'id': x[0], 'word': x[1], 'word_translation': x[2], 'example_use': x[3], 'tags': x[4], 'next_ask_date': x[5], 'ask_results': json.loads(x[6])}, rows))

class WordRepository:
  def __init__(self, connection):
    self.connection = connection
    self._migrate_database()
  
  def _migrate_database(self):
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
    cursor = self.connection.cursor()
    cursor.execute(create_words_table_if_not_exists_query)
    cursor.close()
  
  def save_new_word(self, new_word):
    create_new_word_query = f"""
      INSERT INTO words (word, word_translation, example_use, tags, next_ask_date, ask_results) VALUES
      (?, ?, ?, ?, ?, ?);
    """
    cursor = self.connection.cursor()
    cursor.execute(
      create_new_word_query,
      (new_word['word'], new_word['word_translation'], new_word['example_use'], ",".join(new_word['tags']), new_word['next_ask_date'], json.dumps(new_word['ask_results']))
    )
    self.connection.commit()
    cursor.close()

  def update_word(self, word):
    update_words_query = """
      UPDATE words
      SET word=?, word_translation=?, example_use=?, tags=?, next_ask_date=?, ask_results=?
      WHERE id = ?;
    """
    cursor = self.connection.cursor()
    cursor.execute(update_words_query, (word['word'], word['word_translation'], word['example_use'], word['tags'], word['next_ask_date'], json.dumps(word['ask_results']), word['id']))
    self.connection.commit()
    cursor.close()

  def find_words(self) -> FindWordsBuilder:
    return FindWordsBuilder(self.connection)

sqliteConnection = sqlite3.connect('words.db')

word_repository = WordRepository(sqliteConnection)

##################### UTILS ######################

class ExecutionResult(Enum):
  CONTINUE = 1,
  BREAK = 3,
  ERROR = 3

class Screen():
  def execution_template(self, params):
    return ExecutionResult.ERROR
  
  def display(self, params={}):
    while True:
      result = self.execution_template(params)
      if result is ExecutionResult.CONTINUE:
        continue
      if result is ExecutionResult.BREAK:
        break
      if result is ExecutionResult.ERROR:
        raise Exception("Result of execution is ERROR")
      raise Exception("Bad execute implementation")

  def _clear_screen(self):
    os.system('clear')

  def _get_action(
    self,
    prompt_text = "Enter action: ",
    bad_input_text = "Unknown action. Try again one more time...",
    action_selectors = []
  ):
    while True:
      user_input = input(prompt_text).strip()
      any_sction_selector_matches = any(map(lambda x: re.match(x, user_input), action_selectors))
      if any_sction_selector_matches:
        return user_input
      else:
        print(bad_input_text)
  
  def _truncate_text(self, text, length):
    if length >= len(text):
      return text
    else:
      return text[:length-2] + '..'

################# ADD WORD SCREEN ################

class AddWordScreen(Screen):
  def execution_template(self, params):
    self._clear_screen()
    print("Add new word pannel.")
    print("Follow instructions:")
    new_word = {
      'word': self._prompt_for_word(),
      'word_translation': self._prompt_for_word_translation(),
      'example_use': self._prompt_for_example_use(),
      'tags': self._prompt_for_tags()
    }
    self._clear_screen()
    print("Add new word pannel.")
    print("Does all data correct:")
    print(textwrap.dedent(f"""\
      word: {new_word['word']}
      word translation: {new_word['word_translation']}
      example use: {new_word['example_use']}
      tags: {new_word['tags']}"""
    ))
    action = self._get_action(
      prompt_text = "Actions: 'y' -> data correct, 'n' -> data incorrect, 'e' -> exit to previous menu: ",
      action_selectors = [r"^y$", r"^n$", r"^e$"]
    )
    if action == "y":
      word_repository.save_new_word({
        'word': new_word['word'], 'word_translation': new_word['word_translation'], 'example_use': new_word['example_use'], 'tags': new_word['tags'], 'next_ask_date': date.today(), 'ask_results': []
      })
      input("Word has been added. Press 'Enter' to continue...")
      return ExecutionResult.BREAK
    elif action == "n":
      print("Incorect word data... Try once again.")
    elif action == "e":
      return ExecutionResult.BREAK
    return ExecutionResult.CONTINUE
  
  def _prompt_for_word(self):
    while(True):
      user_input = input("Enter new word: ").strip()
      if len(user_input) == 0:
        print("Word should have at least one letter")
        continue
      same_words = word_repository.find_words().where_word_is(user_input).find()
      if len(same_words) > 0:
        print(f"The same word is alredy defined (with id: {same_words[0]['id']})")
        continue
      return user_input

  def _prompt_for_word_translation(self):
    while(True):
      user_input = input("Enter new word translation: ").strip()
      if len(user_input) > 0:
        return user_input
      else:
        print("Word translation should have at least one letter")

  def _prompt_for_example_use(self):
    user_input = input("Enter new word example use (optional): ").strip()
    return user_input or ""

  def _prompt_for_tags(self):
    tag = self._get_action(
      prompt_text = "Enter tag: 'w' -> word, 'p' -> phersalVerb, 'c' -> collocation: ",
      bad_input_text = "Tag accept one of values: 'w' -> word, 'p' -> phersalVerb, 'c' -> collocation",
      action_selectors = [r"^w$", r"^p$", r"^c$"]
    )
    return {'w': 'word', 'p': 'phersalVerb', 'c': 'collocation'}[tag]

################ EDIT WORD SCREEN ################

class EditWordScreen(Screen):
  def execution_template(self, params):
    id = params['id']
    words = word_repository.find_words().where_id_is(id).find()
    self._clear_screen()
    print(f"Word details page (id: {id})")
    if len(words) == 0:
      print(f"Word with id: {id} does not exists")
      input("Press 'Enter' to go to previous page.")
      return ExecutionResult.BREAK
    else:
      word_to_edit = words[0]
      print(textwrap.dedent(f"""\
        word: {word_to_edit['word']}
        word translation: {word_to_edit['word_translation']}
        example use: {word_to_edit['example_use']}
        tags: {str(word_to_edit['tags'])}"""
      ))
      first_action = self._get_action(
        prompt_text = "Actions: 'd' -> edit, 'e' -> go to previous page: ",
        action_selectors = [r"^d$", r"^e$"]
      )
      if first_action == "e":
        return ExecutionResult.BREAK
      print('Fill new values or accept previous data by leaving empty line:')
      word_to_edit['word'] = self._prompt_for_word(word_to_edit)
      word_to_edit['word_translation'] = self._prompt_for_word_translation(word_to_edit)
      word_to_edit['example_use'] = self._prompt_for_example_use(word_to_edit)
      word_to_edit['tags'] = self._prompt_for_tags(word_to_edit)
      print("Does all edited data correct:")
      print(textwrap.dedent(f"""\
        word: {word_to_edit['word']}
        word translation: {word_to_edit['word_translation']}
        example use: {word_to_edit['example_use']}
        tags: {word_to_edit['tags']}"""
      ))
      second_action = self._get_action(
        prompt_text = "Actions: 'y' -> confirm changes, 'n' -> reject changes, 'e' -> go to previous page: ",
        action_selectors = [r"^y$", r"^n$", r"^e$"]
      )
      if second_action == "y":
        word_repository.update_word(word_to_edit)
        input("Word has been added. Press 'Enter' to continue...")
        return ExecutionResult.BREAK
      elif second_action == "n":
        return ExecutionResult.CONTINUE
      elif second_action == "e":
        return ExecutionResult.BREAK

  def _prompt_for_word(self, word_to_edit):
    while(True):
      user_input = input(f"Enter word [{self._truncate_text(word_to_edit['word'], 15)}]: ").strip()
      if len(user_input) == 0:
        return word_to_edit['word']
      same_words = word_repository.find_words().where_id_is_not(word_to_edit['id']).where_word_is(user_input).find()
      if len(same_words) > 0:
        print(f"The same word is alredy defined (with id: {same_words[0]['id']})")
        continue
      return user_input

  def _prompt_for_word_translation(self, word_to_edit):
    user_input = input(f"Enter word translation [{self._truncate_text(word_to_edit['word_translation'], 15)}]: ").strip()
    return user_input or word_to_edit['word_translation']

  def _prompt_for_example_use(self, word_to_edit):
    user_input = input(f"Enter new word example use [{self._truncate_text(word_to_edit['example_use'], 15)}]: ").strip()
    return user_input or word_to_edit['example_use']

  def _prompt_for_tags(self, word_to_edit):
    tag = self._get_action(
      prompt_text = f"Enter tag: 'w' -> word, 'p' -> phersalVerb, 'c' -> collocation [{self._truncate_text(word_to_edit['tags'], 15)}]: ",
      bad_input_text = "Tag accept one of values: 'w' -> word, 'p' -> phersalVerb, 'c' -> collocation",
      action_selectors = [r"^w$", r"^p$", r"^c$", r"^$"]
    )
    return {'w': 'word', 'p': 'phersalVerb', 'c': 'collocation'}.get(tag, word_to_edit['tags'])

############### LIST WORDS SCREEN ################

class ListWordsScreen(Screen):
  def __init__(self):
    super().__init__()
    self.page = 0
    self.page_size = 10
    self.word_filter = ""

  def execution_template(self, params):
    words_page = word_repository.find_words().with_offset(self.page*self.page_size).with_limit(self.page_size).where_word_like(self.word_filter).find()
    self._clear_screen()
    print("Word list.")
    self._print_table(words_page)
    action = self._get_action(
      prompt_text = "Actions: 'p' -> previous page, 'n' -> next page, 'f' -> apply search filter, id eg. '123' -> edit word with id, 'e' -> exit menu: ",
      action_selectors = [r"^p$", r"^n$", r"^f$", r"^[0-9]+$", r"^e$"]
    )
    if action == "p":
      if self.page == 0:
        input("Can't get previous page because this is the first page. Pres 'Enter' to continue...")
      else:
        self.page = self.page - 1
    elif action == "n":
      if len(words_page) is not self.page_size:
        input("Can't get next page because this is the last page. Pres 'Enter' to continue...")
      else:
        self.page = self.page + 1
    elif action == "f":
      self._clear_screen()
      print("Word list. > Enter word filter")
      self.word_filter = input("Enter word filter. Leave empty to clear filter: ").strip()
      self.page = 0
    elif re.match(r"^[0-9]+$", action):
      EditWordScreen().display({'id': int(action)})
    elif action == "e":
      return ExecutionResult.BREAK
    return ExecutionResult.CONTINUE
  
  def _print_table(self, words_page):
    print(f"| {'id':<6} | {'word':<30} | {'translation':<30} | {'tags':<15} | {'example_use':<35} |")
    print(f"|{'-'*130}|")
    for word in words_page:
      line_parts = [
        f"| {self._truncate_text(str(word['id']), 6):<6} ",
        f"| {self._truncate_text(word['word'], 30):<30} ",
        f"| {self._truncate_text(word['word_translation'], 30):<30} ",
        f"| {self._truncate_text(str(word['tags']), 15):<15} ",
        f"| {self._truncate_text(word['example_use'], 35):<35} |",
      ]
      print("".join(line_parts))
    if len(words_page) == 0:
      print(f"|{'No words to show':^130}|")
    print(f"|{'-'*130}|")
    print(f"""|{f'''page: {self.page}; word filter: {'"' + self.word_filter + '"' if self.word_filter else '---'}''':^130}|""")

################# ASK WORD SCREEN ################

class AskWordScreen(Screen):
  def __init__(self):
    super().__init__()
    self.words_to_ask = self._get_words_to_ask()

  def execution_template(self, params):
    if len(self.words_to_ask) == 0:
      self._clear_screen()
      print("Practice word pannel.")
      print("No more words to ask.")
      input("Press 'Enter' to continue...")
      return ExecutionResult.BREAK
    word = self.words_to_ask.pop(0)
    self._clear_screen()
    print(textwrap.dedent(f"""\
      Practice word pannel.
      word translation: {word['word_translation']}
      tags: {str(word['tags'])}
      word: **********
      example use: **********"""
    ))
    input("Press 'Enter' to show answer...")
    self._clear_screen()
    print(textwrap.dedent(f"""\
      Practice word pannel.
      word translation: {word['word_translation']}
      tags: {str(word['tags'])}
      word: {word['word']}
      example use: {word['example_use']}"""
    ))
    action = self._get_action(
      prompt_text = "Actions: 'y' -> correct answer, 'n' -> incorrect answer, 'd' -> edit word, 'e' -> exit session: ",
      action_selectors = [r"^y$", r"^n$", r"^d$", r"^e$"]
    )
    if action == "y":
      self._mark_as_correct(word)
    elif action == "n":
      self._mark_as_incorrect(word)
    elif action == "d":
      print('This action will terminate learning session. Do you want to continue?')
      edit_action = self._get_action(
        prompt_text = "Actions: 'y' -> yes, 'n' -> no: ",
        action_selectors = [r"^y$", r"^n$"]
      )
      if edit_action == "y":
        EditWordScreen().display({'id': int(word['id'])})
        return ExecutionResult.BREAK
    elif action == "e":
      return ExecutionResult.BREAK
    return ExecutionResult.CONTINUE
  
  def _get_words_to_ask(self):
    words = word_repository.find_words().with_limit(100).where_ask_date_is_due().order_by_ask_date().find()
    random.shuffle(words)
    return words[:20]
  
  def _mark_as_correct(self, word):
    if not word.get('alredy_answered', False):
      word['ask_results'].append({'correct': True, 'asked_at': date.today().strftime("%Y-%m-%d")})
      word['next_ask_date'] = self._calculate_next_ask_date(word)
      word_repository.update_word(word)

  def _mark_as_incorrect(self, word):
    if not word.get('alredy_answered', False):
      word['ask_results'].append({'correct': False, 'asked_at': date.today().strftime("%Y-%m-%d")})
      word['next_ask_date'] = self._calculate_next_ask_date(word)
      word_repository.update_word(word)
    word['alredy_answered'] = True
    self.words_to_ask.append(word)
  
  def _calculate_next_ask_date(self, word):
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

################## MAIN SCREEN ###################

class MainScreen(Screen):
  def execution_template(self, params):
    self._clear_screen()
    print("Main pannel.")
    action = self._get_action(
      prompt_text = "Actions: 'p' -> pratcise words, 'l' -> list words, 'a' -> add new word, 'e' -> exit app: ",
      action_selectors = [r"^p$", r"^l$", r"^a$", r"^e$"]
    )
    if action == "a":
      AddWordScreen().display()
    elif action == "l":
      ListWordsScreen().display()
    elif action == "p":
      AskWordScreen().display()
    elif action == "e":
      print("Bye bye...")
      return ExecutionResult.BREAK
    return ExecutionResult.CONTINUE

###################### MAIN ######################

MainScreen().display()