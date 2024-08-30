import asyncio
import subprocess
import os


async def sign_pdf(input_pdf_path, output_pdf_path, cert_name, password):
    try:
        # Формируем команду для csptest
        command = [
            "csptest", "-sfsign", "-sign",
            "-in", input_pdf_path,
            "-out", output_pdf_path,
            "-my", cert_name,
            "-add"
        ]

        # Запускаем процесс с передачей пароля через stdin
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Отправляем пароль и завершаем ввод
        password_bytes = (password + '\n').encode('utf-8')
        stdout, stderr = await process.communicate(input=password_bytes)

        # Проверка кодировки вывода
        def decode_output(output):
            encodings = ['utf-8', 'cp1251', 'cp866']
            for encoding in encodings:
                try:
                    return output.decode(encoding)
                except UnicodeDecodeError:
                    continue
            return output.decode('utf-8', errors='ignore')  # Fallback с игнорированием ошибок

        stdout_decoded = decode_output(stdout)
        stderr_decoded = decode_output(stderr)

        if process.returncode == 0:
            print(f"PDF успешно подписан и сохранен как {output_pdf_path}")
            print(f"Вывод csptest: {stdout_decoded}")
        else:
            print(f"Ошибка при подписании PDF. Код возврата: {process.returncode}")
            print(f"Ошибка: {stderr_decoded}")
            raise Exception(f"Не удалось подписать PDF. Ошибка: {stderr_decoded}")

    except Exception as e:
        print(f"Ошибка при подписании PDF: {str(e)}")
        raise

# Пример использования:
# asyncio.run(sign_pdf("input.pdf", "signed_output.pdf", "nedra", "ваш_пароль"))
