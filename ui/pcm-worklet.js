class PCMCollector extends AudioWorkletProcessor {
  constructor() { super(); this.samples = new Float32Array(3200); this.offset = 0; this.pending=0; this.dropped=false; this.port.onmessage=()=>{this.pending=Math.max(0,this.pending-1);}; }
  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    for (const value of input) {
      this.samples[this.offset++] = value;
      if (this.offset === this.samples.length) {
        const chunk = this.samples;
        if(this.pending<4){this.port.postMessage({pcm:chunk.buffer,dropped:this.dropped},[chunk.buffer]);this.pending++;this.samples=new Float32Array(3200);this.dropped=false;}else{this.samples.fill(0);this.dropped=true;}
        this.offset=0;
      }
    }
    return true;
  }
}
registerProcessor('pcm-collector', PCMCollector);
