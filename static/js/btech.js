const BRANCHES = {
  aids: {
    label: "AI & Data Science",
    subjects: [
      "Mathematics for AI (Linear Algebra & Calculus)",
      "Python Programming",
      "Data Structures & Algorithms",
      "Statistics & Probability",
      "Machine Learning",
      "Deep Learning & Neural Networks",
      "Natural Language Processing",
      "Computer Vision",
      "Big Data Analytics",
      "Data Warehousing & Mining",
      "Database Management Systems",
      "Cloud Computing",
      "Reinforcement Learning",
      "AI Ethics & Responsible AI"
    ]
  },
  ee: {
    label: "Electrical Engineering",
    subjects: [
      "Circuit Theory & Networks",
      "Electrical Machines",
      "Power Systems",
      "Control Systems",
      "Power Electronics",
      "Signals & Systems",
      "Electromagnetic Field Theory",
      "Measurement & Instrumentation",
      "High Voltage Engineering",
      "Switchgear & Protection",
      "Renewable Energy Systems",
      "Digital Electronics",
      "Microprocessors & Microcontrollers",
      "Electric Drives"
    ]
  },
  mech: {
    label: "Mechatronics",
    subjects: [
      "Engineering Mechanics",
      "Kinematics & Dynamics of Machines",
      "Fluid Mechanics & Hydraulics",
      "Thermodynamics",
      "Sensors & Transducers",
      "Embedded Systems & Microcontrollers",
      "Robotics & Automation",
      "PLC & SCADA",
      "CAD/CAM",
      "Control Systems",
      "Industrial IoT",
      "3D Printing & Additive Manufacturing",
      "Machine Design",
      "Signal Processing"
    ]
  },
  entc: {
    label: "Electronics & Telecommunication",
    subjects: [
      "Basic Electronics",
      "Analog Circuits",
      "Digital Electronics",
      "Signals & Systems",
      "Electronic Devices & Circuits",
      "Communication Systems",
      "Microprocessors & Microcontrollers",
      "VLSI Design",
      "Embedded Systems",
      "Antenna & Wave Propagation",
      "Digital Signal Processing",
      "Wireless Communication",
      "Optical Fiber Communication",
      "Control Systems"
    ]
  },
  mechanical: {
    label: "Mechanical Engineering",
    subjects: [
      "Engineering Mechanics",
      "Thermodynamics",
      "Fluid Mechanics",
      "Strength of Materials",
      "Theory of Machines",
      "Manufacturing Processes",
      "Heat Transfer",
      "Machine Design",
      "CAD/CAM",
      "Industrial Engineering",
      "Refrigeration & Air Conditioning",
      "Automobile Engineering",
      "Metrology & Quality Control",
      "Finite Element Analysis"
    ]
  },
  civil: {
    label: "Civil Engineering",
    subjects: [
      "Engineering Mathematics",
      "Structural Analysis",
      "Concrete Technology",
      "Soil Mechanics & Foundation Engineering",
      "Fluid Mechanics & Hydraulics",
      "Surveying",
      "Transportation Engineering",
      "Environmental Engineering",
      "Steel Structures",
      "Construction Management",
      "Geotechnical Engineering",
      "Water Resources Engineering",
      "Building Materials & Construction",
      "Remote Sensing & GIS"
    ]
  }
};

let selectedBranch = null;
let selectedSubject = null;

function selectBranch(branch, el) {
  selectedBranch = branch;
  selectedSubject = null;

  // highlight card
  document.querySelectorAll('.branch-card').forEach(c => c.classList.remove('selected'));
  el.classList.add('selected');

  // render subjects
  const subjects = BRANCHES[branch].subjects;
  const list = document.getElementById('subjectList');
  list.innerHTML = subjects.map(s =>
    `<button class="subject-pill" onclick="selectSubject('${s.replace(/'/g,"\\'")}', this)">${s}</button>`
  ).join('');

  document.getElementById('subjectSection').style.display = 'block';
  document.getElementById('topicSection').style.display = 'none';
  document.getElementById('btechNotesSection').style.display = 'none';
  document.getElementById('subjectSection').scrollIntoView({ behavior: 'smooth' });
}

function selectSubject(subject, el) {
  selectedSubject = subject;

  document.querySelectorAll('.subject-pill').forEach(p => p.classList.remove('selected'));
  el.classList.add('selected');

  document.getElementById('topicSection').style.display = 'block';
  document.getElementById('btechTopic').value = '';
  document.getElementById('btechNotesSection').style.display = 'none';
  document.getElementById('topicSection').scrollIntoView({ behavior: 'smooth' });
}

async function getBtechNotes() {
  if (!selectedBranch || !selectedSubject) {
    showToast('Please select a branch and subject first');
    return;
  }

  const topic = document.getElementById('btechTopic').value.trim();

  document.getElementById('btechNotesLoader').style.display = 'block';
  document.getElementById('btechNotesSection').style.display = 'none';

  try {
    const res = await fetch('/get_btech_notes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        branch: BRANCHES[selectedBranch].label,
        subject: selectedSubject,
        topic: topic
      })
    });
    const data = await res.json();
    renderNotes(data.notes, 'btechNotesContent');
    document.getElementById('btechNotesSection').style.display = 'block';
    document.getElementById('btechNotesSection').scrollIntoView({ behavior: 'smooth' });
  } catch (e) {
    showToast('Failed to generate notes');
  } finally {
    document.getElementById('btechNotesLoader').style.display = 'none';
  }
}

function renderNotes(raw, targetId) {
  const lines = raw.split('\n');
  let html = '';
  lines.forEach(line => {
    line = line
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code>$1</code>');

    if (/^#{1,2}\s/.test(line)) {
      html += `<h5 class="notes-heading">${line.replace(/^#{1,2}\s/, '')}</h5>`;
    } else if (/^###\s/.test(line)) {
      html += `<h6 class="notes-subheading">${line.replace(/^###\s/, '')}</h6>`;
    } else if (/^\s*[-*•]\s/.test(line)) {
      html += `<div class="notes-bullet"><i class="fa fa-circle-dot me-2"></i>${line.replace(/^\s*[-*•]\s/, '')}</div>`;
    } else if (line.trim() === '') {
      html += '<div class="notes-spacer"></div>';
    } else {
      html += `<p class="notes-para">${line}</p>`;
    }
  });
  document.getElementById(targetId).innerHTML = html;
}

function copyBtechNotes() {
  const text = document.getElementById('btechNotesContent').innerText;
  navigator.clipboard.writeText(text).then(() => showToast('Copied to clipboard!'));
}

function downloadBtechPDF() {
  const { jsPDF } = window.jspdf;
  const doc   = new jsPDF();
  const title = `${BRANCHES[selectedBranch]?.label || 'B.Tech'} — ${selectedSubject || 'Notes'}`;
  const text  = document.getElementById('btechNotesContent').innerText;

  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text(title, 14, 18);

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  const lines = doc.splitTextToSize(text, 182);
  doc.text(lines, 14, 28);
  doc.save(`${selectedSubject || 'btech-notes'}.pdf`);
  showToast('PDF downloaded!');
}
