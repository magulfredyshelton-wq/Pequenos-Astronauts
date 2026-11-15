"""English version of the mission catalogue (incidents, concepts, crew lines, EVA labels).
Keys are the incident ids of catalogo.LINHAS. Fields: title, signal, safe, risky, consequence, recovery.
The Portuguese originals stay in catalogo.py / missao.py; the 2D client asks for lang=en."""

INCIDENTES = {
    # ── travel ──
    "desvio": ("Trajectory drift", "The predicted arrival has left the navigation corridor.", "Measure and correct the trajectory", "Do one single big correction close to arrival", "The drift grew and part of the manoeuvre margin was spent.", "Recompute the route and perform the correction"),
    "impacto": ("Panel impact", "A solar panel gives less power even though the light is good.", "Cut power use and stabilise the energy", "Use the battery to keep the experiment programme going", "The battery lost charge and the ship went into reserve mode.", "Switch off secondary loads and check the reserve"),
    "oxigenio": ("Oxygen leak", "The pressure of the reserve tank is dropping.", "Isolate the leak and switch on the reserve", "Make up for the pressure drop by raising the supply", "Part of the reserve oxygen was lost.", "Seal the compartment and move the crew to the shelter"),
    "co2": ("CO₂ rising", "Carbon dioxide is rising while pressure is stable.", "Inspect the CO₂ removal system", "Raise the oxygen flow to dilute the carbon dioxide", "Filtering stayed degraded and oxygen was wasted.", "Use the matching filter, or isolate the area and test the system"),
    "radiacao": ("Radiation alert", "Sensors detect a burst of solar particles.", "Take the crew to the shielded shelter", "Finish the collection before sheltering the crew", "The accumulated exposure went up.", "Go to the shelter and confirm a safe reading"),
    "atraso": ("Contact interrupted", "The panel warns that the answer from Earth is delayed.", "Run the authorised local procedure", "Hold the repair until Earth confirms", "The delay reduced the response margin.", "Apply the local procedure and send a test message"),
    "sensor_estrelas": ("Star tracker lost its reference", "The orientation sensors disagree and the ship does not know exactly where it points.", "Compare the star tracker with the Sun reference", "Use the orientation computed before the fault and fix it later", "The manoeuvre started badly oriented and used propellant.", "Cancel the burn, check the orientation and realign the ship"),
    "refrigeracao": ("Equipment overheating", "A module's temperature is rising while the rest of the ship is stable.", "Reduce the module's load and inspect the cooling", "Raise the power to finish the module's cycle sooner", "The module entered thermal protection and drew on the energy reserve.", "Keep the critical loads and test the cooling before switching on again"),
    "reciclagem_agua": ("Recycled water not yet verified", "Water from the recovery loop has not passed quality control yet.", "Set the batch apart and use the verified water reserve", "Distribute the treated batch and take a sample in parallel", "The batch became unavailable and the usable reserve fell.", "Isolate the unverified water and repeat treatment and control"),
    # ── Moon ──
    "rochas": ("Rocks at the landing site", "The nominal point has rocks in the descent area.", "Confirm a reachable alternative", "Slow the descent over the nominal point", "The descent was interrupted and used propellant.", "Recompute and verify the alternative zone"),
    "sombra": ("Shadow over the panels", "The terrain is about to block the light reaching the panels.", "Save energy for heating and life support", "Give priority to the workshop and the lab to finish the work", "Autonomy dropped and the workshop shut down.", "Stabilise the energy and restart loads by priority"),
    "relevo": ("Radio blocked by the terrain", "You lost the signal behind a rise.", "Go back to the last point with signal", "Climb the shortest way to the next expected contact point", "The distance to the last contact grew.", "Recover the link and confirm the return autonomy"),
    "rover_lua": ("Dust thrown up by the rover", "A damaged fender throws up dust.", "Stop and check the fender", "Slow the rover down and finish the crossing", "Dust piled up and mobility became limited.", "Clean the rover and fit or improvise a guard"),
    "junta": ("Dust in the joint", "A connection on the equipment is hard to close.", "Clean and test the joint", "Tighten the connection to see if the contact improves", "The connection went out of service.", "Inspect, then replace or repair the connection"),
    "gelo_lua": ("Ice in a shadowed zone", "A promising zone requires crossing cold, sloping ground.", "Prospect with a return margin", "Use the return battery to reach the ice zone first", "The exploration went beyond the battery margin.", "Fall back to a short route and check the return margin"),
    "poeira_antecamara": ("Dust in the airlock", "The crew brings regolith on their boots and suits after the walk.", "Clean the suits in the airlock before going in", "Do the cleaning in the habitat, where there are more tools", "Dust came in with the equipment and reduced operating capacity.", "Isolate the dusty gear, clean it and test the connections"),
    "oscilacao_termica": ("Thermal change on the ridge", "The Sun gets low and an instrument in the shade starts to cool down.", "Reserve energy for the critical instrument", "Split the available energy between the running experiments", "There was not enough energy to stabilise the instrument.", "Switch off secondary loads and bring the instrument back to temperature"),
    "retransmissor": ("Zone with no line of sight", "The crew has to communicate from a spot hidden behind the terrain.", "Schedule contact through a relay", "Agree fixed times to transmit straight to the base", "The crew missed the contact window and the response margin shrank.", "Go back to a point with signal and schedule the next relay pass"),
    # ── Mars ──
    "pouso_marte": ("Landing far from the cargo", "The safest spot is far from the modules.", "Confirm a route to the cargo", "Move the cargo first and mark the route on the way", "The crew lost time and the cargo ended up out of reach.", "Mark a safe route and check the energy margin"),
    "tempestade": ("Dust storm", "Solar panel output is falling.", "Keep only the essential systems running", "Give priority to the workshop and the lab to finish the work", "The battery fell below its margin and the workshop shut down.", "Switch off secondary loads and stabilise the battery"),
    "frio": ("Cold night", "The forecast shows not enough energy for heating.", "Reserve energy for heating", "Finish the experiment and recharge the battery after sunrise", "A sensor restarted during the night.", "Restore the heating and check the sensor"),
    "conjuncao": ("Limited radio window", "The link to Earth will be limited by the position of the Sun.", "Prepare tasks and local procedures", "Keep the decisions for the next contact opportunity", "A task was left without an answer from mission control.", "Run the local procedure and save the telemetry"),
    "gelo_marte": ("Probable ice", "The map shows a promising area, but no water is available yet.", "Confirm a sample and use the water you carried", "Use the reserve on the way to start extraction right now", "The water reserve fell below plan.", "Review the use and confirm extraction and treatment"),
    "roda_marte": ("Wheel wear", "The wheels show wear on rocky ground.", "Pick a route that spares the wheels", "Pick the short route to cut the rover's running time", "The rover lost capacity and left cargo out of reach.", "Cut the load and recover mobility"),
    "painel_marte": ("Dust settled on the panel", "The sky is clear, but the panel still produces little after the storm.", "Check the dust on the panel and turn on energy management", "Resume the planned operations with the light available", "Consumption went over generation and the reserve dropped.", "Save energy, inspect the panel and recover useful generation"),
    "amostra_marte": ("Mixed samples", "Two samples from different places arrived together on the bench.", "Isolate the containers and confirm the origin record", "Prepare one joint sample to speed up the analysis", "The origin reference was lost and another sample must be collected.", "Separate the containers, log the incident and collect a new labelled sample"),
    "abrigo_marte": ("Walk during a solar alert", "A radiation alert arrives while the crew is getting ready to go out.", "Postpone the walk and protect the crew in the shelter", "Limit the walk to short tasks", "Accumulated exposure went up while the crew was outside.", "Go back to the shelter and confirm the readings before rescheduling the walk"),
}

CONCEITOS = {
    "desvio": "Small corrections made early help to save propellant.",
    "impacto": "When production drops, saving energy makes the battery last longer.",
    "oxigenio": "Containing a leak protects the reserve that is still intact.",
    "co2": "Removing CO₂ and supplying oxygen are two different jobs.",
    "radiacao": "The shielded shelter helps to reduce exposure during the alert.",
    "atraso": "The signal takes time to reach Earth, and the answer takes time to come back.",
    "rochas": "A landing zone needs safe ground and room to manoeuvre.",
    "sombra": "Terrain can take light away from the panels while consumption goes on.",
    "relevo": "A rise in the ground can block the radio link.",
    "rover_lua": "A small part can protect the vehicle from the dust the wheels throw up.",
    "junta": "Dust gets in the connections and can make wear worse.",
    "gelo_lua": "Prospecting for ice means keeping energy in reserve for the way back.",
    "pouso_marte": "A safe landing only solves part of the mission: the cargo must be reachable.",
    "tempestade": "Dust can reduce the light on the panels. Cutting consumption protects the reserve.",
    "frio": "Heating is a priority load during the cold night.",
    "conjuncao": "Local procedures let you carry on when the link is limited.",
    "gelo_marte": "A hint of ice only becomes useful water after it is confirmed, extracted and treated.",
    "roda_marte": "A safe route can protect the wheels even when it is longer.",
    "sensor_estrelas": "Comparing known stars helps to work out where the ship is pointing.",
    "refrigeracao": "Thermal control keeps the systems inside their limits.",
    "reciclagem_agua": "Recovered water goes through treatment and checks before it is used.",
    "poeira_antecamara": "Lunar regolith is abrasive. Cleaning before entering reduces wear.",
    "oscilacao_termica": "Local lighting changes the thermal conditions and the energy available.",
    "retransmissor": "A relay lets you keep contact in places outside the line of sight.",
    "painel_marte": "Dust on a panel reduces the light that reaches the solar cells.",
    "amostra_marte": "Isolating samples and recording where they came from avoids cross-contamination.",
    "abrigo_marte": "Exposure time matters. A shielded shelter helps to reduce it."
}

FALAS = {
    "COMANDO": {"PANICO": "Attention, team! We must act now!", "PROTESTO": "This is not going well. We need to change the plan.", "ALIVIO": "Good decision! We can move on to the next task.", "TRISTEZA": "Let's take a pause and review the plan.", "SERENO": "All calm. Let's keep watching.", "NEUTRO": "Waiting for your next decision."},
    "ENGENHARIA": {"PANICO": "We have an alert on the systems. Let's check the readings.", "PROTESTO": "Let's compare the readings before choosing the next step.", "ALIVIO": "The numbers improved. That decision helped a lot.", "TRISTEZA": "Let's confirm what can still be recovered.", "SERENO": "The systems are stable for now.", "NEUTRO": "Watching the systems."},
    "OPERACOES": {"PANICO": "I'm worried. Let's protect the team and follow the plan.", "PROTESTO": "I don't like this decision. Let's think it over.", "ALIVIO": "Phew! I can breathe again.", "TRISTEZA": "We need to get back to working as a team.", "SERENO": "We're fine. We stay together.", "NEUTRO": "Ready to help."},
}

ROTULOS_EVA = {"reparo": "repair", "montagem": "assembly of structures", "instalacao": "equipment installation", "teste": "equipment testing", "ciencia": "science and experiments", "inspecao": "inspection", "geral": "general work outside"}
PAISES_EN = {"EUA": "USA", "Rússia": "Russia", "URSS": "USSR"}
DESTINOS_EN = {"lua": "Moon", "marte": "Mars"}
