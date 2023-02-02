import json
import tkinter as tk
import tkinter.filedialog as fd
from threading import Thread
from bubu_module import BubuLearn, ICSParser


class BubuLearnLoader(tk.Tk):
    def __init__(self, auth_config):
        super().__init__()
        self.title('BubuLearn Loader')
        self.resizable(False, False)
        self.__interface_init()
        self.file_path = None
        self.auth_config = auth_config

    def __interface_init(self):
        self.form_frame = tk.Frame(self, width=450)
        self.file_select_frame = tk.Frame(self.form_frame)
        self.log_frame = tk.Frame(self, width=450, bg='black')

        self.form_frame.pack()
        self.file_select_frame.pack(fill="x", expand=True)
        self.log_frame.pack(fill="both", expand=True)

        self.file_name_label = tk.Label(self.file_select_frame, foreground='black')
        self.file_name_button = tk.Button(self.file_select_frame, text='Выбрать файл', command=self.__select_file)
        self.run_button = tk.Button(self.form_frame, text='Запустить', command=self.__run_load_in_thread)
        self.log = tk.Text(self.log_frame, bg='black', font=("Menlo", 14), state='disabled', wrap="word")

        self.file_name_button.pack(side='left')
        self.file_name_label.pack(side='right')
        self.run_button.pack(pady=10)
        self.log.pack(fill="x", expand=True)
        self.log.tag_config('success', foreground="green")
        self.log.tag_config('error', foreground="red")

    def __select_file(self):
        filename = fd.askopenfilename(
            title='Open a file',
            initialdir='/',
            filetypes=[('calendar files', '*.ics')]
        )
        if filename:
            self.file_path = filename
            self.file_name_label['text'] = filename.split('/')[-1]

    def __print_log(self, message, end="\n", is_error=False):
        self.log['state'] = 'normal'
        self.log.insert(tk.INSERT, message + end, 'error' if is_error else 'success')
        self.log['state'] = 'disabled'

    def __run_load_in_thread(self):
        Thread(target=self.__run_load).start()

    def __run_load(self):
        self.log.delete('1.0', tk.END)
        file_path = self.file_path
        bl = None
        try:
            self.__print_log('загрузка уроков из файла...', end=' ')
            ics_p = ICSParser(file_path)
            events = ics_p.get_events()
            self.__print_log('готово.\nподключение к BubuLearn...', end=' ')
            bl = BubuLearn(config)
            self.__print_log('готово.\nудаление дублирующихся уроков...', end=' ')
            events = bl.drop_duplicates_events(events)
            self.__print_log('готово.\nдобавление уроков...', end=' ')
            for event in events:
                success = bl.add_event(event['phone'], event['date'])
                if not success:
                    self.__print_log(f"\nУрок на {event['date'].strftime('%d.%m.%Y %H:%M:%S')} для {event['phone']} не удалось добавить!", is_error=True)
            self.__print_log('готово.')
        except FileNotFoundError as e:
            self.__print_log(f'\nфайл "{file_path}" не найден!', is_error=True)
        except Exception as e:
            self.__print_log(f'\nошибка: {e}', is_error=True)
        finally:
            self.__print_log('выход из системы...', end=' ')
            if bl is not None:
                bl.logout()
            self.__print_log('готово.')


if __name__ == '__main__':
    config = json.loads(open('config.json', "r").read())
    bll = BubuLearnLoader(config)
    bll.mainloop()
