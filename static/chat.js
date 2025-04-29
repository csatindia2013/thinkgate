let recognition;
let isRecording = false;

function toggleDropdown() {
  const dropdown = document.getElementById('dropdownMenu');
  dropdown.style.display = dropdown.style.display === 'block' ? 'none' : 'block';
}

function getAvatar() {
  const subject = localStorage.getItem('selectedSubject') || 'Math';
  if (subject === 'Math') return 'https://img.icons8.com/ios-filled/50/ffffff/math.png';
  if (subject === 'Science') return 'https://img.icons8.com/ios-filled/50/ffffff/microscope.png';
  if (subject === 'Social Studies') return 'https://img.icons8.com/ios-filled/50/ffffff/globe-earth.png';
  if (subject === 'English') return 'https://img.icons8.com/ios-filled/50/ffffff/book.png';
  return 'https://img.icons8.com/ios-filled/50/ffffff/user.png';
}

function startVoice() {
  const micIcon = document.querySelector('.bi-mic');

  if (!('webkitSpeechRecognition' in window)) {
    alert('Voice recognition not supported.');
    return;
  }

  if (isRecording && recognition) {
    recognition.stop();
    micIcon.classList.remove('pulsing');
    isRecording = false;
    return;
  }

  recognition = new webkitSpeechRecognition();
  recognition.lang = 'en-US';
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    isRecording = true;
    micIcon.classList.add('pulsing');
    console.log("🎤 Recording started...");
  };

  recognition.onresult = function (event) {
    const transcript = event.results[0][0].transcript;
    document.getElementById('userInput').value = transcript;

    // ✅ Auto-send
    setTimeout(() => {
      if (transcript && transcript.length > 0) {
        sendToBackend();
      }
    }, 300);
  };

  recognition.onerror = function (event) {
    console.error("Speech recognition error:", event.error);
  };

  recognition.onend = () => {
    micIcon.classList.remove('pulsing');
    isRecording = false;
    console.log("🛑 Recording stopped.");
  };

  recognition.start();
}

function uploadImage() {
  const input = document.getElementById('imageInput');
  input.setAttribute('accept', 'image/*');
  input.setAttribute('capture', 'environment'); // ✅ Use rear camera on mobile
  input.click();
}

function handleImageUpload() {
  const input = document.getElementById('imageInput');
  const file = input.files[0];

  if (file) {
    const reader = new FileReader();
    reader.onload = function (e) {
      const previewImg = document.createElement('img');
      previewImg.src = e.target.result;
      previewImg.className = "image-preview";
      document.getElementById('chatArea').appendChild(previewImg);
    };
    reader.readAsDataURL(file);

    appendMessage("🖼️ Image captured. Sending to AI Tutor...", 'user');
    sendToBackend(file);
  } else {
    alert("❗ No image captured. Please try again.");
  }

  input.value = ""; // reset input
}



function appendMessage(text, sender) {
  const chatArea = document.getElementById('chatArea');
  const messageDiv = document.createElement('div');
  messageDiv.className = sender === 'user' ? 'message user-message' : 'message bot-message';

  const avatar = document.createElement('img');
  avatar.src = getAvatar();

  const messageContent = document.createElement('div');
  messageContent.className = 'message-content';
  messageContent.innerText = text;

  messageDiv.appendChild(avatar);
  messageDiv.appendChild(messageContent);
  chatArea.appendChild(messageDiv);
  chatArea.scrollTop = chatArea.scrollHeight;
}

function typeMessage(text) {
  const chatArea = document.getElementById('chatArea');
  const messageDiv = document.createElement('div');
  messageDiv.className = 'message bot-message';

  const avatar = document.createElement('img');
  avatar.src = getAvatar();

  const messageContent = document.createElement('div');
  messageContent.className = 'message-content';
  messageDiv.appendChild(avatar);
  messageDiv.appendChild(messageContent);
  chatArea.appendChild(messageDiv);

  let i = 0;
  const maxTime = 2000;
  const totalChars = text.length;
  const delay = Math.max(5, Math.floor(maxTime / totalChars));

  const interval = setInterval(() => {
    if (i < totalChars) {
      messageContent.innerText += text[i];
      chatArea.scrollTop = chatArea.scrollHeight;
      i++;
    } else {
      clearInterval(interval);
      MathJax.typesetPromise();
      hideSpinner();
    }
  }, delay);
}

function sendToBackend(uploadedFile = null) {
  const input = document.getElementById('userInput').value.trim();
  if (!input && !uploadedFile) {
    alert("Please type a question or upload an image.");
    return;
  }

  if (!uploadedFile) {
    appendMessage(input, 'user');
  }

  const formData = new FormData();
  if (uploadedFile) {
    formData.append('cameraInput', uploadedFile);
  } else {
    formData.append('userInput', input);
  }

  document.getElementById('userInput').value = '';
  showSpinner();

  fetch('/chat', {
    method: 'POST',
    body: formData
  })
    .then(response => response.json())
    .then(data => {
      typeMessage(data.reply || "❗No reply received.");
      if (data.youtube_embed) {
        document.getElementById('youtubeVideo').innerHTML = `
          <div style="text-align: left; margin-top: 10px;">
            <iframe width="400" height="225" src="${data.youtube_embed}" frameborder="0" allowfullscreen></iframe>
          </div>
        `;
      } else {
        document.getElementById('youtubeVideo').innerHTML = '';
      }
    })
    .catch(error => {
      console.error('Error from backend:', error);
      typeMessage("❗Something went wrong.");
      hideSpinner();
    });
}

function showSpinner() {
  document.getElementById('loadingSpinner').style.display = 'block';
}
function hideSpinner() {
  document.getElementById('loadingSpinner').style.display = 'none';
}

function updateSelectedInfo() {
  const name = localStorage.getItem('studentName') || 'Student';
  const board = localStorage.getItem('selectedBoard') || 'CBSE';
  const classSelected = localStorage.getItem('selectedClass') || 'Class 8';
  const subject = localStorage.getItem('selectedSubject') || 'Math';
  document.getElementById('selectedInfo').innerText = `Hi ${name}! | Board: ${board} | Class: ${classSelected} | Subject: ${subject}`;
  document.getElementById('welcomeMessage').innerText = `Hi ${name}! Welcome to ThinkGate! 🎓`;
}

function showProfileModal() {
  document.getElementById('modalName').value = localStorage.getItem('studentName') || "";
  document.getElementById('modalBoardSelect').value = localStorage.getItem('selectedBoard') || "";
  document.getElementById('modalClassSelect').value = localStorage.getItem('selectedClass') || "";
  document.getElementById('modalSubjectSelect').value = localStorage.getItem('selectedSubject') || "";

  var myModal = new bootstrap.Modal(document.getElementById('profileModal'));
  myModal.show();
}

function saveProfile() {
  const name = document.getElementById('modalName').value.trim();
  const board = document.getElementById('modalBoardSelect').value;
  const classSelected = document.getElementById('modalClassSelect').value;
  const subject = document.getElementById('modalSubjectSelect').value;

  if (!name || !board || !classSelected || !subject) {
    alert("Please fill your Name, Board, Class, and Subject.");
    return;
  }

  localStorage.setItem('studentName', name);
  localStorage.setItem('selectedBoard', board);
  localStorage.setItem('selectedClass', classSelected);
  localStorage.setItem('selectedSubject', subject);

  updateSelectedInfo();
  saveProfileToServer();

  var myModal = bootstrap.Modal.getInstance(document.getElementById('profileModal'));
  myModal.hide();
}

function saveProfileToServer() {
  const board = localStorage.getItem('selectedBoard');
  const studentClass = localStorage.getItem('selectedClass');
  const subject = localStorage.getItem('selectedSubject');

  fetch('/save_profile', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `board=${encodeURIComponent(board)}&class=${encodeURIComponent(studentClass)}&subject=${encodeURIComponent(subject)}`
  });
}

function saveSelection() {
  const board = document.getElementById('boardSelect').value;
  const classSelected = document.getElementById('classSelect').value;

  localStorage.setItem('selectedBoard', board);
  localStorage.setItem('selectedClass', classSelected);

  updateSelectedInfo();
}

document.addEventListener('click', function (event) {
  const dropdown = document.getElementById('dropdownMenu');
  const button = event.target.closest('.icon-button');
  if (!dropdown.contains(event.target) && !button) {
    dropdown.style.display = 'none';
  }
});

window.onload = function () {
  updateSelectedInfo();
  const name = localStorage.getItem('studentName');
  const board = localStorage.getItem('selectedBoard');
  const classSelected = localStorage.getItem('selectedClass');
  const subject = localStorage.getItem('selectedSubject');
  if (!name || !board || !classSelected || !subject) showProfileModal();
};
