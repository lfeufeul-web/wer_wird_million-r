import re
with open('main.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('alignment="center"', 'alignment=ft.MainAxisAlignment.CENTER')
text = text.replace('alignment="space-between"', 'alignment=ft.MainAxisAlignment.SPACE_BETWEEN')
text = text.replace('alignment="spaceBetween"', 'alignment=ft.MainAxisAlignment.SPACE_BETWEEN')
text = text.replace('alignment="start"', 'alignment=ft.MainAxisAlignment.START')
text = text.replace('alignment="end"', 'alignment=ft.MainAxisAlignment.END')
text = text.replace('horizontal_alignment="center"', 'horizontal_alignment=ft.CrossAxisAlignment.CENTER')

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Alignments fixed")
