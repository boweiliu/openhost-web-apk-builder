const phoneUrl=document.querySelector('#phone-url');
const phoneQr=document.querySelector('#phone-qr');
const copyPageLink=document.querySelector('#copy-page-link');
const copyStatus=document.querySelector('#phone-copy-status');
function updatePhoneLink(){
  const address=window.location.href;
  phoneUrl.href=address;phoneUrl.textContent=address;
  phoneQr.src=`/qr.png?${new URLSearchParams({url:address})}`;
}
phoneQr.addEventListener('error',()=>{phoneQr.hidden=true;document.querySelector('#qr-fallback').hidden=false;});
phoneQr.addEventListener('load',()=>{phoneQr.hidden=false;document.querySelector('#qr-fallback').hidden=true;});
copyPageLink.addEventListener('click',async()=>{
  try{await navigator.clipboard.writeText(window.location.href);copyStatus.textContent='Link copied';}
  catch{copyStatus.textContent='Press and hold the link to copy it.';}
});
window.addEventListener('hashchange',updatePhoneLink);
window.addEventListener('popstate',updatePhoneLink);
updatePhoneLink();
