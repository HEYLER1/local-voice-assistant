"""Conservative speech gate at 16 kHz. Keeps timestamps and discards no files."""
import numpy as np
import webrtcvad


class SpeechGate:
    def __init__(self):
        self.vad=webrtcvad.Vad(3)
        self.hangover=0
        self.voiced=[]
        self.offset=0

    def filter(self,samples):
        source=np.clip(samples,-1,1)
        frames=[]
        for start in range(0,len(source),320):
            frame=source[start:start+320]
            padded=np.pad(frame,(0,320-len(frame)))
            rms=float(np.sqrt(np.mean(padded*padded)))
            spectrum=np.abs(np.fft.rfft(padded*np.hanning(320)))**2
            tonal=float(np.sum(np.partition(spectrum,-3)[-3:])/(np.sum(spectrum)+1e-12))>.9
            pcm=(padded*32767).astype('<i2').tobytes()
            frames.append(rms>.002 and not tonal and self.vad.is_speech(pcm,16000))
        # Isolated clicks/beeps must not open the gate. Keep complete chunks to
        # preserve quiet consonants around speech; a short tail avoids clipping.
        speech=sum(frames)>=min(3,len(frames))
        if speech:
            self.hangover=2
            self.voiced.append((self.offset,self.offset+len(source)/16000))
        passed=speech or self.hangover>0
        if not speech:self.hangover=max(0,self.hangover-1)
        self.offset+=len(source)/16000
        return source.copy() if passed else np.zeros_like(source)

    def supports_line(self,start,duration):
        end=start+duration if duration>0 else self.offset
        return sum(max(0,min(end,b)-max(start,a)) for a,b in self.voiced)>=.08
