# Diary

Heidi’s Diary

Clockify: https://app.clockify.me/shared/69dca0027c7d08e9ae36fa42

---

## Diary Description

This diary documents the development of an AI project manager and portfolio generator application. The goal of the project was to build an application that utilizes artificial intelligence to analyze GitHub repositories and automatically generate documentation, analyses, and portfolios for the user.

The technologies used in the project included Python, FastAPI, Streamlit, and the Gemini API. The work was carried out as pair programming, where I was mainly responsible for the frontend part.

---

## Week 05  
**Hours: 2h**

- We started planning the project topic and idea  
- We decided to develop an AI project manager and portfolio generator application  
- We defined the project scope as two main parts: AI-assisted project management and an automatic portfolio generator  
- We selected the tech stack: Python, FastAPI, Streamlit, Gemini Flash, GitHub API, SQLite, and Docker  
- We agreed on a total workload estimate of 200 hours (100h per student) and a schedule of approximately 1–8 weeks  
- We created a project issue on GitHub and agreed on task division: Joni handles backend and API integrations, and Heidi handles the Streamlit implementation  

The initial phase of the project was clear and well-organized. The topic felt suitably challenging but feasible.

---

## Week 6  
**Hours: 9h**

- The project was set up and we decided to build it on GitHub  
- At this stage, we continued planning the project structure and how different API interfaces would work together  
- I built the MKDocs documentation base and modified it to work with GitHub Pages  
- I also started writing the project plan  

The project structure began to take shape more clearly. Building documentation early made later work easier.

---

## Week 7  
**Hours: 10h**

- The week started with drafting the requirements and reflecting on them  
- I wrote the introduction section of the project  
- I finalized both the requirements specification and the project plan  
- I also figured out how to create and use the Gemini API key  
- I created the GitHub API key  

Setting up API keys required some investigation and brought unexpected challenges, but in the end everything worked.

---

## Week 8  
**Hours: 13h**

- The Gemini API key was created, initialized, and tested  
- The Streamlit application was also initialized and its basic structure created  
- At this stage, only the `github-service` was available, so I started building the Dashboard page in Streamlit based on that API  
- I also initialized other pages such as AI Analysis, Documentation, and Portfolio  
- Later, additional services were introduced and I integrated them into Streamlit  

This was the first clear development phase where integrating API services into the UI was both interesting and educational.

---

## Week 9  
**Hours: 9h**

- Improved the Dashboard page (appearance and functionality)  
- Fixed bugs in Streamlit  
- Updated and cleaned up the tech stack for better functionality  
- Reviewed and corrected fork-related information for clarity  
- Improved Streamlit session state handling  

Refining the UI turned out to be time-consuming, and I wanted to ensure a user-friendly and clear UX.

---

## Week 10  
**Hours: 7h**

- Completed the Dashboard page and ensured data displayed correctly  
- Verified that commit and contributor lists worked properly  
- Fixed data visualization to show accurate information  
- Started developing other pages  

Ensuring that the data matched what is shown on GitHub was time-consuming and somewhat challenging.

---

## Week 11  
**Hours: 8h**

- Improved README generation between the docs service and Streamlit  
- Enhanced loading and display logic of the README page  
- Improved project plan generation for more consistent and usable output  
- Implemented saving generated documents in session state to avoid regeneration  
- Tested and fixed download functionality  

At this stage, the focus was on usability. I refined AI prompts to produce more accurate and consistent results.

---

## Week 12  
**Hours: 12h**

- Improved portfolio generation in both content and appearance  
- Enhanced the visual design of the portfolio page  
- Improved LinkedIn post generation to better match LinkedIn style  
- Refined the LinkedIn prompt for better results  
- Added a “Next Steps” section to the AI analysis page  

Prompt tuning was crucial—small changes had a big impact on output quality and accuracy.

---

## Week 13  
**Hours: 8h 15min**

- Cleaned and refactored Streamlit code for better structure and maintainability  
- Improved UI consistency and visual polish across pages  
- Resolved merge conflicts and ensured correct integration of changes  
- Fixed bugs caused by merge conflicts  
- Updated the root-level README.md to match the final architecture  

Resolving merge conflicts was challenging due to their number, but it improved my understanding of version control.

---

## Week 14  
**Hours: 20h**

- Added new API requests after noticing UI features not working as intended  
- Made small database changes to ensure correct data storage  
- Created a new “History” page to track database content  
- Finalized the commit section on the Analysis page  
- Built a Code Quality feature where Gemini evaluates repository code  
- Fixed as many bugs as possible for the demo  

The final phase was intense. I learned to prioritize critical fixes and focus on overall functionality.

---

## Week 15  
**Hours: 5h**

- Prepared and recorded the final demo  
- Reviewed project documentation thoroughly  
- Updated missing or incomplete documentation sections  
- Ensured GitHub Pages worked correctly  
- Prepared final project submission  

The project concluded in a controlled and structured way. Documentation became especially important.

---

# Summary

During the project, I learned significantly about:

- API integrations and connecting them to a UI  
- Using AI (Gemini) for content generation and analytics  
- The importance of prompts and how small changes affect outcomes  
- Using session state for state management in Streamlit  

Main challenges included:

- API setup  
- Bug fixing  
- UI refinement  

If I were to do the project again:

- I would plan the architecture more thoroughly from the beginning  
- I would create a clearer backlog/task plan early on  
- I would allocate more time for UI and UX design  

Overall, the project was successful. The result was a functional and versatile application that met the objectives and significantly improved my skills.