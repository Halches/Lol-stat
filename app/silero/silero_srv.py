# Сервер озвучки Silero для LoL Helper. Запускается программой один раз и держит модель в памяти.
# Вход (stdin, по строке JSON): {"text": ..., "speaker": ..., "out": путь.wav, "rate": 1.0}. Выход: "ok" или "err <текст>".
import json, os, sys, wave

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    sys.stdin.reconfigure(encoding='utf-8'); sys.stdout.reconfigure(encoding='utf-8')
    import torch
    torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))
    model = torch.package.PackageImporter(os.path.join(HERE, 'v5_ru.pt')).load_pickle('tts_models', 'model')
    model.to(torch.device('cpu'))
    print('ready', flush=True)
    for line in sys.stdin:
        try:
            q = json.loads(line)
            sr = 48000
            audio = model.apply_tts(text=q['text'], speaker=q.get('speaker', 'kseniya'), sample_rate=sr,
                                    put_accent=True, put_yo=True)
            pcm = (audio.clamp(-1, 1) * 32767).to(torch.int16).numpy().tobytes()
            with wave.open(q['out'], 'wb') as w:
                w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(pcm)
            print('ok', flush=True)
        except Exception as e:
            print('err', str(e).replace('\n', ' '), flush=True)


if __name__ == '__main__':
    main()
