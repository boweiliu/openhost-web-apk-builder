const form=document.querySelector('#build-form');
const feedback=document.querySelector('#feedback');
const list=document.querySelector('#builds');
const button=document.querySelector('#submit');
const states={queued:'Waiting to build',building:'Building your APK…',ready:'Ready to install',failed:'Build failed',interrupted:'Build interrupted'};
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
async function refresh(){
  try{
    const response=await fetch('/api/builds');if(!response.ok)throw Error('Sign in again to see your apps.');
    const jobs=await response.json();list.replaceChildren();document.querySelector('#count').textContent=jobs.length?`${jobs.length} build${jobs.length===1?'':'s'}`:'';
    if(!jobs.length)list.append(node('p','Your first app will appear here.','empty'));
    for(const job of jobs){
      const card=node('article',undefined,'card');const info=node('div',undefined,'card-info');
      info.append(node('h3',job.name),node('p',new URL(job.url).host));
      if(job.error)info.append(node('p',job.error,'error'));
      if(job.size)info.append(node('p',`${(job.size/1048576).toFixed(1)} MB · Version ${job.version}`));
      const links=node('div',undefined,'card-links');
      for(const [label,path] of [['Source',`/builds/${job.id}/source`],['Build log',`/builds/${job.id}/log`]]){const a=node('a',label);a.href=path;links.append(a);}info.append(links);card.append(info);
      if(job.state==='ready'){const a=node('a','Download APK','download');a.href=`/builds/${job.id}/app.apk`;card.append(a);}else card.append(node('span',states[job.state]||job.state,`tag ${job.state}`));
      list.append(card);
    }
  }catch(error){feedback.textContent=error.message;}
}
form.addEventListener('submit',async event=>{
  event.preventDefault();button.disabled=true;feedback.textContent='Sending your build…';
  try{const response=await fetch('/api/builds',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:form.elements.namedItem('url').value,name:form.elements.namedItem('name').value})});const data=await response.json();if(!response.ok)throw Error(data.error||'Could not create the app.');feedback.textContent='Your app is queued. You can leave this page while it builds.';await refresh();}
  catch(error){feedback.textContent=error.message;}finally{button.disabled=false;}
});
refresh();setInterval(refresh,4000);
